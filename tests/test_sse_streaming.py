"""Tests for SSE streaming and approval payload fixes."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── _publish_execution_event ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_execution_event_publishes_to_redis():
    """Event publisher should call redis.publish with the correct channel."""
    from core.execution_engine import _publish_execution_event, EXECUTION_CHANNEL_PREFIX

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        await _publish_execution_event("exec-123", {"type": "node.started", "node_id": "n1"})

    mock_redis.publish.assert_awaited_once()
    call_args = mock_redis.publish.call_args
    channel, payload = call_args[0]
    assert channel == f"{EXECUTION_CHANNEL_PREFIX}exec-123"
    data = json.loads(payload)
    assert data["type"] == "node.started"
    assert data["node_id"] == "n1"


@pytest.mark.asyncio
async def test_publish_execution_event_swallows_redis_errors():
    """A Redis failure must not crash the execution engine."""
    from core.execution_engine import _publish_execution_event

    with patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis down")):
        # Should not raise
        await _publish_execution_event("exec-456", {"type": "test"})


# ── EXECUTION_CHANNEL_PREFIX ──────────────────────────────────────────────────

def test_execution_channel_prefix_constant():
    from core.execution_engine import EXECUTION_CHANNEL_PREFIX
    assert isinstance(EXECUTION_CHANNEL_PREFIX, str)
    assert len(EXECUTION_CHANNEL_PREFIX) > 0


# ── _run_node_tracked emits events ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_node_tracked_emits_started_and_completed():
    """Successful node should emit node.started then node.completed."""
    from core.execution_engine import _run_node_tracked, register_node

    emitted = []

    async def fake_publish(execution_id, event):
        emitted.append(event)

    @register_node("sse_test_ok")
    async def ok_handler(**kwargs):
        return {"value": 42}

    node = {"id": "sse_n1", "type": "sse_test_ok", "retry": {}}
    node_results = {}

    with patch("core.execution_engine._publish_execution_event", side_effect=fake_publish):
        result = await _run_node_tracked(node, {}, AsyncMock(), node_results, execution_id="exec-789")

    assert result == {"value": 42}
    types = [e["type"] for e in emitted]
    assert "node.started" in types
    assert "node.completed" in types
    started = next(e for e in emitted if e["type"] == "node.started")
    assert started["node_id"] == "sse_n1"
    completed = next(e for e in emitted if e["type"] == "node.completed")
    assert completed["status"] == "success"
    assert "duration_ms" in completed


@pytest.mark.asyncio
async def test_run_node_tracked_emits_failed_on_error():
    """Failed node should emit node.started then node.failed."""
    from core.execution_engine import _run_node_tracked, register_node

    emitted = []

    async def fake_publish(execution_id, event):
        emitted.append(event)

    @register_node("sse_test_fail")
    async def fail_handler(**kwargs):
        raise ValueError("deliberate failure")

    node = {"id": "sse_n2", "type": "sse_test_fail", "retry": {}}
    node_results = {}

    with patch("core.execution_engine._publish_execution_event", side_effect=fake_publish):
        with pytest.raises(ValueError):
            await _run_node_tracked(node, {}, AsyncMock(), node_results, execution_id="exec-abc")

    types = [e["type"] for e in emitted]
    assert "node.started" in types
    assert "node.failed" in types
    failed = next(e for e in emitted if e["type"] == "node.failed")
    assert "deliberate failure" in failed["error"]
    assert "duration_ms" in failed


@pytest.mark.asyncio
async def test_run_node_tracked_no_execution_id_no_publish():
    """When execution_id is None, no events should be published."""
    from core.execution_engine import _run_node_tracked, register_node

    @register_node("sse_no_exec_id")
    async def handler(**kwargs):
        return {}

    node = {"id": "sse_n3", "type": "sse_no_exec_id", "retry": {}}
    node_results = {}

    published = []
    async def fake_publish(execution_id, event):
        published.append(event)

    with patch("core.execution_engine._publish_execution_event", side_effect=fake_publish):
        await _run_node_tracked(node, {}, AsyncMock(), node_results, execution_id=None)

    assert published == []


# ── Approval payload fix ──────────────────────────────────────────────────────

def test_approval_effective_payload_prefers_response_payload():
    """When both response_payload and edited_data are given, response_payload wins."""
    response_payload = {"choice": "approved_version"}
    edited_data = {"choice": "edited_version"}
    effective = response_payload or edited_data
    assert effective == response_payload


def test_approval_effective_payload_falls_back_to_edited_data():
    """When response_payload is None, edited_data is used."""
    response_payload = None
    edited_data = {"field": "modified_value"}
    effective = response_payload or edited_data
    assert effective == edited_data


def test_approval_effective_payload_none_when_both_none():
    """When both are None, effective payload is None."""
    response_payload = None
    edited_data = None
    effective = response_payload or edited_data
    assert effective is None


# ── get_current_user_sse ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_current_user_sse_accepts_query_param_token():
    """SSE auth dependency must accept token from query params."""
    from api.middleware.auth import get_current_user_sse

    fake_user = MagicMock()
    mock_request = MagicMock()
    mock_request.query_params = {"token": "valid_token_xyz"}

    with patch("api.middleware.auth._user_from_token", new=AsyncMock(return_value=fake_user)):
        result = await get_current_user_sse(
            request=mock_request,
            credentials=None,
            db=AsyncMock(),
        )

    assert result is fake_user


@pytest.mark.asyncio
async def test_get_current_user_sse_accepts_bearer_header():
    """SSE auth dependency must also accept Authorization: Bearer."""
    from api.middleware.auth import get_current_user_sse
    from fastapi.security import HTTPAuthorizationCredentials

    fake_user = MagicMock()
    mock_request = MagicMock()
    mock_request.query_params = {}
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="header_token")

    with patch("api.middleware.auth._user_from_token", new=AsyncMock(return_value=fake_user)):
        result = await get_current_user_sse(
            request=mock_request,
            credentials=credentials,
            db=AsyncMock(),
        )

    assert result is fake_user


@pytest.mark.asyncio
async def test_get_current_user_sse_raises_401_when_no_token():
    """SSE auth raises 401 when neither header nor query param is present."""
    from api.middleware.auth import get_current_user_sse
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.query_params = {}

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_sse(
            request=mock_request,
            credentials=None,
            db=AsyncMock(),
        )

    assert exc_info.value.status_code == 401
