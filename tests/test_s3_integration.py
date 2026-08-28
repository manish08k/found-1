"""
Tests for the AWS S3 integration, using moto to mock AWS itself (this
sandbox's network can't reach amazonaws.com — same constraint as the
other new integrations, different mocking tool since this one uses
boto3's SDK rather than raw httpx).
"""
import pytest
from moto import mock_aws
import boto3

from integrations.aws_s3_.handler import (
    s3_put_object, s3_get_object, s3_list_objects, s3_generate_presigned_url,
    test_connection as s3_test_connection, MAX_GET_BYTES,
)


class FakeDB:
    pass


FAKE_CREDS = {"access_key_id": "testing", "secret_access_key": "testing", "region": "us-east-1"}


@pytest.fixture
def s3_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return FAKE_CREDS
    monkeypatch.setattr("integrations.aws_s3_.handler.get_credential_data", fake_get_credential_data)


@pytest.fixture
def moto_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket="test-bucket")
        yield "test-bucket"


@pytest.mark.asyncio
async def test_s3_put_and_get_object(s3_creds, moto_bucket):
    put_result = await s3_put_object(
        {"bucket": moto_bucket, "key": "hello.txt", "body": "Hello, world!"}, {}, "cred1", FakeDB()
    )
    assert put_result["bucket"] == moto_bucket
    assert put_result["key"] == "hello.txt"
    assert put_result["etag"]  # moto returns a real-shaped ETag

    get_result = await s3_get_object({"bucket": moto_bucket, "key": "hello.txt"}, {}, "cred1", FakeDB())
    assert get_result["content"] == "Hello, world!"
    assert get_result["encoding"] == "utf-8"


@pytest.mark.asyncio
async def test_s3_get_object_binary_falls_back_to_base64(s3_creds, moto_bucket):
    await s3_put_object({"bucket": moto_bucket, "key": "bin.dat", "body": b"\xff\xfe\x00\x01"}, {}, "cred1", FakeDB())
    result = await s3_get_object({"bucket": moto_bucket, "key": "bin.dat"}, {}, "cred1", FakeDB())
    assert result["encoding"] == "base64"


@pytest.mark.asyncio
async def test_s3_get_object_rejects_oversized_file(s3_creds, moto_bucket):
    await s3_put_object({"bucket": moto_bucket, "key": "big.txt", "body": "x" * (MAX_GET_BYTES + 1)}, {}, "cred1", FakeDB())
    with pytest.raises(ValueError, match="byte limit"):
        await s3_get_object({"bucket": moto_bucket, "key": "big.txt"}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
async def test_s3_list_objects(s3_creds, moto_bucket):
    await s3_put_object({"bucket": moto_bucket, "key": "reports/jan.csv", "body": "a"}, {}, "cred1", FakeDB())
    await s3_put_object({"bucket": moto_bucket, "key": "reports/feb.csv", "body": "b"}, {}, "cred1", FakeDB())
    await s3_put_object({"bucket": moto_bucket, "key": "other/file.txt", "body": "c"}, {}, "cred1", FakeDB())

    result = await s3_list_objects({"bucket": moto_bucket, "prefix": "reports/"}, {}, "cred1", FakeDB())
    keys = {o["key"] for o in result["objects"]}
    assert keys == {"reports/jan.csv", "reports/feb.csv"}


@pytest.mark.asyncio
async def test_s3_generate_presigned_url(s3_creds, moto_bucket):
    await s3_put_object({"bucket": moto_bucket, "key": "file.txt", "body": "content"}, {}, "cred1", FakeDB())
    result = await s3_generate_presigned_url({"bucket": moto_bucket, "key": "file.txt"}, {}, "cred1", FakeDB())
    assert result["url"].startswith("https://")
    assert moto_bucket in result["url"]


@pytest.mark.asyncio
async def test_s3_put_object_requires_fields(s3_creds, moto_bucket):
    with pytest.raises(ValueError, match="bucket"):
        await s3_put_object({}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
async def test_s3_test_connection_success(moto_bucket):
    await s3_test_connection(FAKE_CREDS)  # should not raise — list_buckets works against the moto mock
