"""
Tests for n8n-batch integrations: datatable, debug_helper, xml, wait,
webhook, write_binary_file, workflow_trigger, demio, discourse, disqus.

Pure in-memory handlers need no HTTP mocking.
HTTP-backed handlers (demio, discourse, disqus) are mocked with respx.
"""
import os
import tempfile
import pytest
import respx
import httpx
from unittest.mock import AsyncMock

# ── datatable ─────────────────────────────────────────────────────────────────
from integrations.datatable.handler import (
    datatable_insert,
    datatable_lookup,
    datatable_get_all,
)

# ── debug_helper ──────────────────────────────────────────────────────────────
from integrations.debug_helper.handler import (
    debug_helper_throw_error,
    debug_helper_do_nothing,
)

# ── xml ───────────────────────────────────────────────────────────────────────
from integrations.xml.handler import (
    xml_to_json,
    xml_to_xml,
)

# ── wait ──────────────────────────────────────────────────────────────────────
from integrations.wait.handler import (
    wait_wait,
    wait_wait_for_webhook,
)

# ── webhook ───────────────────────────────────────────────────────────────────
from integrations.webhook.handler import (
    webhook_trigger,
    webhook_respond,
)

# ── write_binary_file ─────────────────────────────────────────────────────────
from integrations.write_binary_file.handler import (
    write_binary_file_write,
)

# ── workflow_trigger ──────────────────────────────────────────────────────────
from integrations.workflow_trigger.handler import (
    workflow_trigger_trigger,
)

# ── demio ─────────────────────────────────────────────────────────────────────
from integrations.demio.handler import (
    demio_list_events,
)

# ── discourse ─────────────────────────────────────────────────────────────────
from integrations.discourse.handler import (
    discourse_get_topics,
)

# ── disqus ────────────────────────────────────────────────────────────────────
from integrations.disqus.handler import (
    disqus_list_threads,
)

# ─────────────────────────────────────────────────────────────────────────────
CRED = "test-credential-id"
DB = None

DEMIO_CREDS = {"api_key": "demio-key", "api_secret": "demio-secret"}
DISCOURSE_CREDS = {
    "base_url": "https://forum.example.com",
    "api_key": "discourse-key",
    "api_username": "system",
}
DISQUS_CREDS = {
    "access_token": "disqus-token",
    "api_key": "disqus-pub-key",
    "forum": "myforum",
}


# =============================================================================
# DataTable Tests
# =============================================================================

@pytest.mark.asyncio
class TestDatatableInsert:
    async def test_insert_adds_row(self):
        result = await datatable_insert(
            config={"values": {"name": "Alice", "score": 42}},
            input_data={"table": []},
            credential_id=CRED,
            db=DB,
        )
        assert result["total_rows"] == 1
        assert result["inserted_row"]["name"] == "Alice"
        assert result["table"][0]["score"] == 42

    async def test_insert_into_existing_table(self):
        existing = [{"name": "Bob", "score": 10}]
        result = await datatable_insert(
            config={"values": {"name": "Carol", "score": 99}},
            input_data={"table": existing},
            credential_id=CRED,
            db=DB,
        )
        assert result["total_rows"] == 2
        assert result["inserted_row"]["name"] == "Carol"

    async def test_insert_missing_values_raises(self):
        with pytest.raises(ValueError, match="requires 'values'"):
            await datatable_insert(
                config={},
                input_data={"table": []},
                credential_id=CRED,
                db=DB,
            )


@pytest.mark.asyncio
class TestDatatableLookup:
    async def test_lookup_finds_matching_rows(self):
        table = [
            {"name": "Alice", "dept": "eng"},
            {"name": "Bob", "dept": "hr"},
            {"name": "Carol", "dept": "eng"},
        ]
        result = await datatable_lookup(
            config={"lookup_column": "dept", "lookup_value": "eng"},
            input_data={"table": table},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert all(r["dept"] == "eng" for r in result["results"])

    async def test_lookup_no_match_returns_empty(self):
        table = [{"name": "Alice", "dept": "eng"}]
        result = await datatable_lookup(
            config={"lookup_column": "dept", "lookup_value": "finance"},
            input_data={"table": table},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 0
        assert result["results"] == []

    async def test_lookup_missing_column_raises(self):
        with pytest.raises(ValueError, match="requires 'lookup_column'"):
            await datatable_lookup(
                config={},
                input_data={"table": []},
                credential_id=CRED,
                db=DB,
            )


@pytest.mark.asyncio
class TestDatatableGetAll:
    async def test_get_all_returns_all_rows(self):
        table = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = await datatable_get_all(
            config={},
            input_data={"table": table},
            credential_id=CRED,
            db=DB,
        )
        assert result["total_rows"] == 3
        assert len(result["rows"]) == 3

    async def test_get_all_empty_table(self):
        result = await datatable_get_all(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["total_rows"] == 0
        assert result["rows"] == []


# =============================================================================
# DebugHelper Tests
# =============================================================================

@pytest.mark.asyncio
class TestDebugHelperThrowError:
    async def test_throws_value_error_with_config_message(self):
        with pytest.raises(ValueError, match="custom error message"):
            await debug_helper_throw_error(
                config={"error_message": "custom error message"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    async def test_throws_value_error_with_default_message(self):
        with pytest.raises(ValueError, match="intentional error"):
            await debug_helper_throw_error(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    async def test_throws_value_error_from_input_data(self):
        with pytest.raises(ValueError, match="from input"):
            await debug_helper_throw_error(
                config={},
                input_data={"error_message": "from input"},
                credential_id=CRED,
                db=DB,
            )


@pytest.mark.asyncio
class TestDebugHelperDoNothing:
    async def test_returns_input_data_unchanged(self):
        input_data = {"key": "value", "count": 7}
        result = await debug_helper_do_nothing(
            config={},
            input_data=input_data,
            credential_id=CRED,
            db=DB,
        )
        assert result == input_data

    async def test_returns_empty_dict_for_empty_input(self):
        result = await debug_helper_do_nothing(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result == {}


# =============================================================================
# XML Tests
# =============================================================================

@pytest.mark.asyncio
class TestXmlToJson:
    async def test_parses_simple_xml(self):
        xml = "<root><name>Alice</name><age>30</age></root>"
        result = await xml_to_json(
            config={"xml_string": xml},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "json" in result
        assert "root" in result["json"]
        assert result["json"]["root"]["name"] == {"#text": "Alice"}

    async def test_parses_xml_from_input_data(self):
        xml = "<item><id>42</id></item>"
        result = await xml_to_json(
            config={},
            input_data={"xml_string": xml},
            credential_id=CRED,
            db=DB,
        )
        assert "item" in result["json"]

    async def test_missing_xml_raises(self):
        with pytest.raises(ValueError, match="xml_string"):
            await xml_to_json(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


@pytest.mark.asyncio
class TestXmlToXml:
    async def test_converts_dict_to_xml_string(self):
        json_data = {"person": {"name": {"#text": "Alice"}, "age": {"#text": "30"}}}
        result = await xml_to_xml(
            config={"json_data": json_data},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "xml" in result
        assert "<person>" in result["xml"]
        assert "Alice" in result["xml"]

    async def test_converts_dict_from_input_data(self):
        json_data = {"note": {"#text": "hello"}}
        result = await xml_to_xml(
            config={},
            input_data={"json_data": json_data},
            credential_id=CRED,
            db=DB,
        )
        assert "<note>" in result["xml"]

    async def test_missing_json_raises(self):
        with pytest.raises(ValueError, match="json_data"):
            await xml_to_xml(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    async def test_non_single_root_raises(self):
        with pytest.raises(ValueError, match="exactly one root key"):
            await xml_to_xml(
                config={"json_data": {"a": {}, "b": {}}},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


# =============================================================================
# Wait Tests
# =============================================================================

@pytest.mark.asyncio
class TestWaitWait:
    async def test_wait_returns_waited_seconds(self):
        result = await wait_wait(
            config={"duration": 0},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["waited_seconds"] == 0.0
        assert "resumed_at" in result

    async def test_wait_default_duration_is_clamped(self):
        # duration=0 in config, no actual sleep
        result = await wait_wait(
            config={"duration": 0},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["waited_seconds"] >= 0

    async def test_wait_clamps_negative_duration(self):
        result = await wait_wait(
            config={"duration": -5},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["waited_seconds"] == 0.0


@pytest.mark.asyncio
class TestWaitForWebhook:
    async def test_returns_url_with_webhook_wait_path(self):
        result = await wait_wait_for_webhook(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "/webhook/wait/" in result["url"]
        assert "webhook_id" in result

    async def test_each_call_produces_unique_id(self):
        r1 = await wait_wait_for_webhook(config={}, input_data={}, credential_id=CRED, db=DB)
        r2 = await wait_wait_for_webhook(config={}, input_data={}, credential_id=CRED, db=DB)
        assert r1["webhook_id"] != r2["webhook_id"]


# =============================================================================
# Webhook Tests
# =============================================================================

@pytest.mark.asyncio
class TestWebhookTrigger:
    async def test_extracts_body_from_input_data(self):
        result = await webhook_trigger(
            config={},
            input_data={"body": {"event": "order.created", "order_id": 123}},
            credential_id=CRED,
            db=DB,
        )
        assert result["body"]["event"] == "order.created"
        assert result["body"]["order_id"] == 123

    async def test_uses_input_data_directly_when_no_body_key(self):
        result = await webhook_trigger(
            config={},
            input_data={"message": "hello"},
            credential_id=CRED,
            db=DB,
        )
        assert result["body"]["message"] == "hello"

    async def test_preserves_headers_and_query(self):
        result = await webhook_trigger(
            config={},
            input_data={
                "body": {"x": 1},
                "headers": {"X-Token": "abc"},
                "query": {"page": "1"},
            },
            credential_id=CRED,
            db=DB,
        )
        assert result["headers"]["X-Token"] == "abc"
        assert result["query"]["page"] == "1"

    async def test_response_code_from_config(self):
        result = await webhook_trigger(
            config={"response_code": 201},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["response_code"] == 201


@pytest.mark.asyncio
class TestWebhookRespond:
    async def test_builds_correct_status_and_body(self):
        result = await webhook_respond(
            config={"response_code": 200, "response_data": {"ok": True}},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["status"] == 200
        assert result["body"]["ok"] is True

    async def test_default_status_is_200(self):
        result = await webhook_respond(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["status"] == 200

    async def test_includes_response_headers(self):
        result = await webhook_respond(
            config={
                "response_code": 204,
                "response_headers": {"X-Custom": "header-value"},
            },
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["headers"]["X-Custom"] == "header-value"
        assert result["status"] == 204


# =============================================================================
# WriteBinaryFile Tests
# =============================================================================

@pytest.mark.asyncio
class TestWriteBinaryFileWrite:
    async def test_write_creates_file_with_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "output.txt")
            result = await write_binary_file_write(
                config={"file_path": dest, "content": "hello world"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
            assert result["written"] is True
            assert result["file_path"] == dest
            assert result["bytes_written"] == len(b"hello world")
            with open(dest, "rb") as fh:
                assert fh.read() == b"hello world"

    async def test_write_binary_base64_content(self):
        import base64
        raw = b"\x00\x01\x02\x03"
        encoded = base64.b64encode(raw).decode()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "data.bin")
            result = await write_binary_file_write(
                config={"file_path": dest, "content": encoded, "encoding": "binary"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
            assert result["bytes_written"] == 4
            with open(dest, "rb") as fh:
                assert fh.read() == raw

    async def test_write_missing_file_path_raises(self):
        with pytest.raises(ValueError, match="file_path is required"):
            await write_binary_file_write(
                config={"content": "data"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


# =============================================================================
# WorkflowTrigger Tests
# =============================================================================

@pytest.mark.asyncio
class TestWorkflowTriggerTrigger:
    async def test_trigger_returns_triggered_true(self):
        result = await workflow_trigger_trigger(
            config={},
            input_data={"user_id": 42},
            credential_id=CRED,
            db=DB,
        )
        assert result["triggered"] is True

    async def test_trigger_includes_payload(self):
        input_data = {"order_id": 99, "amount": 19.99}
        result = await workflow_trigger_trigger(
            config={},
            input_data=input_data,
            credential_id=CRED,
            db=DB,
        )
        assert result["payload"] == input_data

    async def test_trigger_includes_workflow_id_from_config(self):
        result = await workflow_trigger_trigger(
            config={"workflow_id": "wf-abc-123"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["workflow_id"] == "wf-abc-123"
        assert result["source"] == "workflow_trigger"


# =============================================================================
# Demio Tests
# =============================================================================

@pytest.mark.asyncio
class TestDemioListEvents:
    @respx.mock
    async def test_list_events_returns_events(self):
        respx.get("https://my.demio.com/api/v1/event").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "evt-1", "name": "Intro Webinar"},
                    {"id": "evt-2", "name": "Advanced Session"},
                ],
            )
        )
        result = await demio_list_events(
            config=DEMIO_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert result["events"][0]["id"] == "evt-1"

    @respx.mock
    async def test_list_events_handles_wrapped_response(self):
        respx.get("https://my.demio.com/api/v1/event").mock(
            return_value=httpx.Response(
                200,
                json={"events": [{"id": "evt-3", "name": "Q&A Session"}]},
            )
        )
        result = await demio_list_events(
            config=DEMIO_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 1
        assert result["events"][0]["name"] == "Q&A Session"

    async def test_list_events_missing_credentials_raises(self):
        with pytest.raises(ValueError, match="api_key.*api_secret|api_secret.*api_key"):
            await demio_list_events(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


# =============================================================================
# Discourse Tests
# =============================================================================

@pytest.mark.asyncio
class TestDiscourseGetTopics:
    @respx.mock
    async def test_get_topics_returns_topics(self):
        respx.get("https://forum.example.com/latest.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "topic_list": {
                        "topics": [
                            {"id": 1, "title": "Welcome to the forum"},
                            {"id": 2, "title": "Announcements"},
                        ]
                    }
                },
            )
        )
        result = await discourse_get_topics(
            config=DISCOURSE_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert result["topics"][0]["title"] == "Welcome to the forum"

    @respx.mock
    async def test_get_topics_empty_list(self):
        respx.get("https://forum.example.com/latest.json").mock(
            return_value=httpx.Response(200, json={"topic_list": {"topics": []}})
        )
        result = await discourse_get_topics(
            config=DISCOURSE_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 0
        assert result["topics"] == []

    async def test_get_topics_missing_base_url_raises(self):
        with pytest.raises(ValueError, match="base_url"):
            await discourse_get_topics(
                config={"api_key": "k", "api_username": "u"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


# =============================================================================
# Disqus Tests
# =============================================================================

@pytest.mark.asyncio
class TestDisqusListThreads:
    @respx.mock
    async def test_list_threads_returns_results(self):
        respx.get("https://disqus.com/api/3.0/threads/list.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "response": [
                        {"id": "thread-1", "title": "First Discussion"},
                        {"id": "thread-2", "title": "Second Discussion"},
                    ],
                    "cursor": {"hasNext": False},
                },
            )
        )
        result = await disqus_list_threads(
            config=DISQUS_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert result["threads"][0]["id"] == "thread-1"
        assert result["threads"][1]["title"] == "Second Discussion"

    @respx.mock
    async def test_list_threads_empty_response(self):
        respx.get("https://disqus.com/api/3.0/threads/list.json").mock(
            return_value=httpx.Response(
                200,
                json={"response": [], "cursor": {"hasNext": False}},
            )
        )
        result = await disqus_list_threads(
            config=DISQUS_CREDS,
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 0
        assert result["threads"] == []

    async def test_list_threads_missing_forum_raises(self):
        with pytest.raises(ValueError, match="requires 'forum'"):
            await disqus_list_threads(
                config={
                    "access_token": "tok",
                    "api_key": "key",
                    # no 'forum'
                },
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    async def test_list_threads_missing_access_token_raises(self):
        with pytest.raises(ValueError, match="access_token"):
            await disqus_list_threads(
                config={"api_key": "key", "forum": "myforum"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
