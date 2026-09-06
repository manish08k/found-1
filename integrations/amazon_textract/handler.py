"""Amazon Textract integration for document text extraction and analysis."""
import base64
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _get_client(creds: dict):
    if not HAS_BOTO3:
        raise ImportError("boto3 is required. Install with: pip install boto3")
    return boto3.client(
        "textract",
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


def _build_document(merged: dict) -> dict:
    """Build Textract Document parameter from config."""
    s3_bucket = merged.get("s3_bucket")
    s3_key = merged.get("s3_key")
    if s3_bucket and s3_key:
        doc = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
        version = merged.get("s3_version")
        if version:
            doc["S3Object"]["Version"] = version
        return doc
    doc_bytes = merged.get("document_bytes") or merged.get("bytes")
    if doc_bytes:
        if isinstance(doc_bytes, str):
            doc_bytes = base64.b64decode(doc_bytes)
        return {"Bytes": doc_bytes}
    raise ValueError("document source required: provide 's3_bucket'+'s3_key' or 'document_bytes'")


@register_node("amazon_textract.detect_document_text")
async def detect_document_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Detect and extract all text from a document using Textract."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged

    def _detect():
        client = _get_client(creds)
        document = _build_document(merged)
        response = client.detect_document_text(Document=document)
        blocks = response.get("Blocks", [])
        lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE" and "Text" in b]
        return {
            "blocks": blocks,
            "lines": lines,
            "full_text": "\n".join(lines),
            "page_count": response.get("DocumentMetadata", {}).get("Pages", 1),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _detect)


@register_node("amazon_textract.analyze_document")
async def analyze_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Analyze a document for forms, tables, and signatures."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    feature_types = merged.get("feature_types", ["FORMS", "TABLES"])

    def _analyze():
        client = _get_client(creds)
        document = _build_document(merged)
        response = client.analyze_document(Document=document, FeatureTypes=feature_types)
        blocks = response.get("Blocks", [])
        # Extract key-value pairs from FORMS
        key_values = {}
        key_blocks = {b["Id"]: b for b in blocks if b.get("BlockType") == "KEY_VALUE_SET" and "KEY" in b.get("EntityTypes", [])}
        value_blocks = {b["Id"]: b for b in blocks if b.get("BlockType") == "KEY_VALUE_SET" and "VALUE" in b.get("EntityTypes", [])}
        word_map = {b["Id"]: b.get("Text", "") for b in blocks if b.get("BlockType") == "WORD"}

        def get_text_from_block(block):
            words = []
            for rel in block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for child_id in rel["Ids"]:
                        if child_id in word_map:
                            words.append(word_map[child_id])
            return " ".join(words)

        for key_id, key_block in key_blocks.items():
            key_text = get_text_from_block(key_block)
            for rel in key_block.get("Relationships", []):
                if rel["Type"] == "VALUE":
                    for val_id in rel["Ids"]:
                        val_block = value_blocks.get(val_id)
                        if val_block:
                            key_values[key_text] = get_text_from_block(val_block)

        return {
            "blocks": blocks,
            "key_value_pairs": key_values,
            "page_count": response.get("DocumentMetadata", {}).get("Pages", 1),
            "feature_types": feature_types,
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _analyze)


@register_node("amazon_textract.start_document_analysis")
async def start_document_analysis(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Start asynchronous document analysis for large multi-page documents."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    s3_bucket = merged.get("s3_bucket")
    s3_key = merged.get("s3_key")
    if not s3_bucket or not s3_key:
        raise ValueError("start_document_analysis requires 's3_bucket' and 's3_key'")
    feature_types = merged.get("feature_types", ["FORMS", "TABLES"])
    notification_channel = merged.get("notification_channel")  # {"SNSTopicArn": ..., "RoleArn": ...}
    output_bucket = merged.get("output_s3_bucket")
    output_prefix = merged.get("output_s3_prefix")

    def _start():
        client = _get_client(creds)
        kwargs = {
            "DocumentLocation": {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
            "FeatureTypes": feature_types,
        }
        if notification_channel:
            kwargs["NotificationChannel"] = notification_channel
        if output_bucket:
            kwargs["OutputConfig"] = {"S3Bucket": output_bucket}
            if output_prefix:
                kwargs["OutputConfig"]["S3Prefix"] = output_prefix
        client_request_token = merged.get("client_request_token")
        if client_request_token:
            kwargs["ClientRequestToken"] = client_request_token
        response = client.start_document_analysis(**kwargs)
        return {"job_id": response.get("JobId"), "status": "IN_PROGRESS"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _start)
