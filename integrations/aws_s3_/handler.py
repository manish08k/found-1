"""
AWS S3 integration — put/get/list objects. Uses boto3 (already a
dependency for the KMS envelope-encryption backend,
credentials/envelope.py) rather than aioboto3, to avoid adding another
heavy dependency for one integration — boto3 calls are blocking, so each
one runs via asyncio.to_thread rather than blocking the event loop that
every other concurrent workflow execution shares.

Credential fields: {"access_key_id": "...", "secret_access_key": "...",
"region": "us-east-1"}. Recommend a bucket-scoped IAM policy for this
key, same "least privilege" guidance as the database integration's
recommendation for a read-only DB user — a workflow node credential
should have the narrowest access that does its job, not your account's
admin keys.
"""
import asyncio
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

MAX_LIST_KEYS = 1000  # hard cap so a workflow can't accidentally page through a bucket with millions of objects
MAX_GET_BYTES = 10 * 1024 * 1024  # 10MB — this is a workflow node, not a bulk-file-transfer tool; use presigned URLs for anything bigger


def _client(creds: dict):
    import boto3
    return boto3.client(
        "s3",
        aws_access_key_id=creds.get("access_key_id"),
        aws_secret_access_key=creds.get("secret_access_key"),
        region_name=creds.get("region", "us-east-1"),
    )


@register_node("s3.put_object")
async def s3_put_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    bucket = config.get("bucket") or input_data.get("bucket")
    key = config.get("key") or input_data.get("key")
    body = config.get("body") if config.get("body") is not None else input_data.get("body", "")
    if not bucket or not key:
        raise ValueError("s3.put_object requires 'bucket' and 'key'")

    creds = await get_credential_data(credential_id, db)
    body_bytes = body.encode() if isinstance(body, str) else body

    def _do_put():
        client = _client(creds)
        return client.put_object(Bucket=bucket, Key=key, Body=body_bytes)

    result = await asyncio.to_thread(_do_put)
    return {"etag": result.get("ETag", "").strip('"'), "bucket": bucket, "key": key}


@register_node("s3.get_object")
async def s3_get_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    bucket = config.get("bucket") or input_data.get("bucket")
    key = config.get("key") or input_data.get("key")
    if not bucket or not key:
        raise ValueError("s3.get_object requires 'bucket' and 'key'")

    creds = await get_credential_data(credential_id, db)

    def _do_get():
        client = _client(creds)
        obj = client.head_object(Bucket=bucket, Key=key)
        if obj["ContentLength"] > MAX_GET_BYTES:
            raise ValueError(
                f"s3.get_object: object is {obj['ContentLength']} bytes, over the "
                f"{MAX_GET_BYTES} byte limit for this node — use a presigned URL "
                f"(s3.generate_presigned_url) for larger files instead of pulling "
                f"the whole thing through a workflow node."
            )
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    content = await asyncio.to_thread(_do_get)
    try:
        text = content.decode("utf-8")
        return {"bucket": bucket, "key": key, "content": text, "encoding": "utf-8"}
    except UnicodeDecodeError:
        import base64
        return {"bucket": bucket, "key": key, "content": base64.b64encode(content).decode(), "encoding": "base64"}


@register_node("s3.list_objects")
async def s3_list_objects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    bucket = config.get("bucket") or input_data.get("bucket")
    prefix = config.get("prefix", input_data.get("prefix", ""))
    max_keys = min(int(config.get("max_keys", 100)), MAX_LIST_KEYS)
    if not bucket:
        raise ValueError("s3.list_objects requires 'bucket'")

    creds = await get_credential_data(credential_id, db)

    def _do_list():
        client = _client(creds)
        return client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)

    result = await asyncio.to_thread(_do_list)
    objects = [
        {"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"].isoformat()}
        for o in result.get("Contents", [])
    ]
    return {"objects": objects, "truncated": result.get("IsTruncated", False)}


@register_node("s3.generate_presigned_url")
async def s3_generate_presigned_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    bucket = config.get("bucket") or input_data.get("bucket")
    key = config.get("key") or input_data.get("key")
    expires_in = min(int(config.get("expires_in_seconds", 3600)), 7 * 24 * 3600)  # cap at 7 days, S3's own max for SigV4
    if not bucket or not key:
        raise ValueError("s3.generate_presigned_url requires 'bucket' and 'key'")

    creds = await get_credential_data(credential_id, db)

    def _do_presign():
        client = _client(creds)
        return client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in)

    url = await asyncio.to_thread(_do_presign)
    return {"url": url, "expires_in_seconds": expires_in}


async def test_connection(creds: dict) -> None:
    def _do_test():
        client = _client(creds)
        client.list_buckets()

    await asyncio.to_thread(_do_test)
