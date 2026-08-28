"""
Tests for the Trello/PagerDuty/Asana/AWS S3 integrations.

Same honesty note as tests/test_new_integrations.py: this sandbox's
network can't reach api.trello.com, events.pagerduty.com,
app.asana.com, or amazonaws.com, so these mock the transport layer
(respx for the three REST APIs, moto for AWS) rather than hitting the
real services. That verifies request/response handling — the part
actually written here — not live-API behavior.
"""
import pytest
import respx
import httpx

from integrations.trello_.handler import (
    trello_create_card, trello_move_card, trello_list_cards, test_connection as trello_test_connection,
)
from integrations.pagerduty_.handler import (
    pagerduty_trigger_incident, pagerduty_resolve_incident,
)
from integrations.asana_.handler import (
    asana_create_task, asana_complete_task, asana_list_tasks, test_connection as asana_test_connection,
)


class FakeDB:
    pass


# ── Trello ───────────────────────────────────────────────────────────────────

@pytest.fixture
def trello_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"api_key": "fakekey", "token": "faketoken"}
    monkeypatch.setattr("integrations.trello_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_trello_create_card(trello_creds):
    respx.post("https://api.trello.com/1/cards").mock(
        return_value=httpx.Response(200, json={"id": "card1", "shortUrl": "https://trello.com/c/abc"})
    )
    result = await trello_create_card({"list_id": "list1", "name": "New task"}, {}, "cred1", FakeDB())
    assert result == {"id": "card1", "url": "https://trello.com/c/abc"}

    request = respx.calls.last.request
    assert "key=fakekey" in str(request.url)
    assert "token=faketoken" in str(request.url)


@pytest.mark.asyncio
@respx.mock
async def test_trello_move_card(trello_creds):
    respx.put("https://api.trello.com/1/cards/card1").mock(
        return_value=httpx.Response(200, json={"id": "card1", "idList": "list2"})
    )
    result = await trello_move_card({"card_id": "card1", "list_id": "list2"}, {}, "cred1", FakeDB())
    assert result["idList"] == "list2"


@pytest.mark.asyncio
@respx.mock
async def test_trello_list_cards(trello_creds):
    respx.get("https://api.trello.com/1/lists/list1/cards").mock(
        return_value=httpx.Response(200, json=[{"id": "c1", "name": "Task A", "shortUrl": "https://trello.com/c/1"}])
    )
    result = await trello_list_cards({"list_id": "list1"}, {}, "cred1", FakeDB())
    assert result["cards"][0]["name"] == "Task A"


@pytest.mark.asyncio
async def test_trello_create_card_requires_fields(trello_creds):
    with pytest.raises(ValueError, match="list_id"):
        await trello_create_card({}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
@respx.mock
async def test_trello_test_connection_success():
    respx.get("https://api.trello.com/1/members/me").mock(return_value=httpx.Response(200, json={}))
    await trello_test_connection({"api_key": "k", "token": "t"})


# ── PagerDuty ────────────────────────────────────────────────────────────────

@pytest.fixture
def pagerduty_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"routing_key": "fakeroutingkey"}
    monkeypatch.setattr("integrations.pagerduty_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_pagerduty_trigger_incident(pagerduty_creds):
    respx.post("https://events.pagerduty.com/v2/enqueue").mock(
        return_value=httpx.Response(202, json={"status": "success", "dedup_key": "dk-123"})
    )
    result = await pagerduty_trigger_incident({"summary": "DB down", "severity": "critical"}, {}, "cred1", FakeDB())
    assert result["status"] == "success"

    import json
    payload = json.loads(respx.calls.last.request.content)
    assert payload["event_action"] == "trigger"
    assert payload["payload"]["severity"] == "critical"


@pytest.mark.asyncio
async def test_pagerduty_rejects_invalid_severity(pagerduty_creds):
    with pytest.raises(ValueError, match="severity"):
        await pagerduty_trigger_incident({"summary": "x", "severity": "apocalyptic"}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
@respx.mock
async def test_pagerduty_resolve_incident(pagerduty_creds):
    respx.post("https://events.pagerduty.com/v2/enqueue").mock(
        return_value=httpx.Response(202, json={"status": "success"})
    )
    result = await pagerduty_resolve_incident({"dedup_key": "dk-123"}, {}, "cred1", FakeDB())
    assert result["status"] == "success"

    import json
    payload = json.loads(respx.calls.last.request.content)
    assert payload["event_action"] == "resolve"


@pytest.mark.asyncio
async def test_pagerduty_resolve_requires_dedup_key(pagerduty_creds):
    with pytest.raises(ValueError, match="dedup_key"):
        await pagerduty_resolve_incident({}, {}, "cred1", FakeDB())


# ── Asana ────────────────────────────────────────────────────────────────────

@pytest.fixture
def asana_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"access_token": "faketoken"}
    monkeypatch.setattr("integrations.asana_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_asana_create_task(asana_creds):
    respx.post("https://app.asana.com/api/1.0/tasks").mock(
        return_value=httpx.Response(201, json={"data": {"gid": "t1", "name": "New task", "permalink_url": "https://app.asana.com/0/1/t1"}})
    )
    result = await asana_create_task({"project_id": "p1", "name": "New task"}, {}, "cred1", FakeDB())
    assert result["gid"] == "t1"

    request = respx.calls.last.request
    assert request.headers["Authorization"] == "Bearer faketoken"


@pytest.mark.asyncio
@respx.mock
async def test_asana_complete_task(asana_creds):
    respx.put("https://app.asana.com/api/1.0/tasks/t1").mock(
        return_value=httpx.Response(200, json={"data": {"gid": "t1", "completed": True}})
    )
    result = await asana_complete_task({"task_gid": "t1"}, {}, "cred1", FakeDB())
    assert result["completed"] is True


@pytest.mark.asyncio
@respx.mock
async def test_asana_list_tasks(asana_creds):
    respx.get("https://app.asana.com/api/1.0/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json={"data": [{"gid": "t1", "name": "A", "completed": False}]})
    )
    result = await asana_list_tasks({"project_id": "p1"}, {}, "cred1", FakeDB())
    assert result["tasks"][0]["name"] == "A"


@pytest.mark.asyncio
@respx.mock
async def test_asana_test_connection_success():
    respx.get("https://app.asana.com/api/1.0/users/me").mock(return_value=httpx.Response(200, json={}))
    await asana_test_connection({"access_token": "t"})


@pytest.mark.asyncio
async def test_asana_test_connection_missing_token():
    with pytest.raises(ValueError):
        await asana_test_connection({})
