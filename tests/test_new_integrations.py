"""
Tests for the Stripe/Email(SendGrid)/Twilio/Jira integrations.

These use respx to mock the HTTP layer rather than calling the real
third-party APIs — this sandbox's network egress is restricted to
package registries only (no api.stripe.com, api.sendgrid.com,
api.twilio.com, or *.atlassian.net), so a live-API test the way the
MySQL integration got isn't possible here. Mocking the HTTP boundary
still verifies the part that's actually ours to get right: request
construction (URLs, auth headers/params, payload shape) and response
parsing — the same class of bug the MySQL testing found (a bad
pool_pre_ping interaction) wouldn't be caught here, but a wrong auth
scheme, wrong field name, or bad payload shape would be.
"""
import pytest
import respx
import httpx

from integrations.stripe_.handler import (
    stripe_create_payment_link, stripe_get_customer, stripe_list_charges,
    stripe_create_refund, test_connection as stripe_test_connection,
)
from integrations.email_.handler import email_send, test_connection as sendgrid_test_connection
from integrations.twilio_.handler import twilio_send_sms, test_connection as twilio_test_connection
from integrations.jira_.handler import (
    jira_create_issue, jira_search_issues, jira_add_comment,
    test_connection as jira_test_connection,
)


class FakeDB:
    """Stand-in for the AsyncSession param — never actually queried because
    get_credential_data is monkeypatched in these tests."""
    pass


@pytest.fixture
def stripe_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"api_key": "sk_test_fake123"}
    monkeypatch.setattr("integrations.stripe_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_stripe_create_payment_link(stripe_creds):
    respx.post("https://api.stripe.com/v1/payment_links").mock(
        return_value=httpx.Response(200, json={"id": "plink_123", "url": "https://buy.stripe.com/xyz"})
    )
    result = await stripe_create_payment_link({"price_id": "price_1AbC", "quantity": 2}, {}, "cred1", FakeDB())
    assert result == {"id": "plink_123", "url": "https://buy.stripe.com/xyz"}

    # Confirm the request actually carried the right auth + payload shape.
    request = respx.calls.last.request
    assert request.headers["Authorization"].startswith("Basic ")  # httpx encodes (api_key, "") as Basic auth
    body = request.content.decode()
    assert "line_items%5B0%5D%5Bprice%5D=price_1AbC" in body
    assert "line_items%5B0%5D%5Bquantity%5D=2" in body


@pytest.mark.asyncio
@respx.mock
async def test_stripe_get_customer(stripe_creds):
    respx.get("https://api.stripe.com/v1/customers/cus_123").mock(
        return_value=httpx.Response(200, json={"id": "cus_123", "email": "a@b.com", "name": "Alice", "balance": 0, "currency": "usd"})
    )
    result = await stripe_get_customer({"customer_id": "cus_123"}, {}, "cred1", FakeDB())
    assert result["email"] == "a@b.com"


@pytest.mark.asyncio
@respx.mock
async def test_stripe_list_charges(stripe_creds):
    respx.get("https://api.stripe.com/v1/charges").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "ch_1", "amount": 500, "currency": "usd", "status": "succeeded", "paid": True}], "has_more": False})
    )
    result = await stripe_list_charges({"limit": 5}, {}, "cred1", FakeDB())
    assert result["charges"][0]["id"] == "ch_1"
    assert result["has_more"] is False


@pytest.mark.asyncio
@respx.mock
async def test_stripe_create_refund(stripe_creds):
    respx.post("https://api.stripe.com/v1/refunds").mock(
        return_value=httpx.Response(200, json={"id": "re_1", "status": "succeeded", "amount": 500})
    )
    result = await stripe_create_refund({"charge_id": "ch_1"}, {}, "cred1", FakeDB())
    assert result["status"] == "succeeded"


@pytest.mark.asyncio
async def test_stripe_create_payment_link_requires_price_id(stripe_creds):
    with pytest.raises(ValueError, match="price_id"):
        await stripe_create_payment_link({}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
@respx.mock
async def test_stripe_test_connection_success():
    respx.get("https://api.stripe.com/v1/balance").mock(return_value=httpx.Response(200, json={}))
    await stripe_test_connection({"api_key": "sk_test_fake"})  # should not raise


@pytest.mark.asyncio
async def test_stripe_test_connection_missing_key():
    with pytest.raises(ValueError):
        await stripe_test_connection({})


# ── Email (SendGrid) ─────────────────────────────────────────────────────────

@pytest.fixture
def sendgrid_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"api_key": "SG.fake123"}
    monkeypatch.setattr("integrations.email_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_email_send(sendgrid_creds):
    respx.post("https://api.sendgrid.com/v3/mail/send").mock(
        return_value=httpx.Response(202, headers={"X-Message-Id": "msg-123"})
    )
    result = await email_send(
        {"to": "recipient@example.com", "from": "sender@example.com", "subject": "Hi", "body": "Hello"},
        {}, "cred1", FakeDB(),
    )
    assert result["status_code"] == 202
    assert result["message_id"] == "msg-123"

    request = respx.calls.last.request
    assert request.headers["Authorization"] == "Bearer SG.fake123"


@pytest.mark.asyncio
async def test_email_send_rejects_invalid_address(sendgrid_creds):
    with pytest.raises(ValueError, match="not a valid email"):
        await email_send({"to": "not-an-email", "from": "sender@example.com", "subject": "Hi", "body": "x"}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
async def test_email_send_requires_subject(sendgrid_creds):
    with pytest.raises(ValueError, match="subject"):
        await email_send({"to": "a@b.com", "from": "c@d.com", "subject": "", "body": "x"}, {}, "cred1", FakeDB())


# ── Twilio ───────────────────────────────────────────────────────────────────

@pytest.fixture
def twilio_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"account_sid": "ACfake123", "auth_token": "tokenfake"}
    monkeypatch.setattr("integrations.twilio_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_twilio_send_sms(twilio_creds):
    respx.post("https://api.twilio.com/2010-04-01/Accounts/ACfake123/Messages.json").mock(
        return_value=httpx.Response(201, json={"sid": "SM123", "status": "queued"})
    )
    result = await twilio_send_sms({"to": "+14155552671", "from": "+14155550000", "body": "Hello"}, {}, "cred1", FakeDB())
    assert result == {"sid": "SM123", "status": "queued"}


@pytest.mark.asyncio
async def test_twilio_rejects_non_e164_number(twilio_creds):
    with pytest.raises(ValueError, match="E.164"):
        await twilio_send_sms({"to": "5551234", "from": "+14155550000", "body": "Hi"}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
async def test_twilio_rejects_oversized_body(twilio_creds):
    with pytest.raises(ValueError, match="1600"):
        await twilio_send_sms({"to": "+14155552671", "from": "+14155550000", "body": "x" * 2000}, {}, "cred1", FakeDB())


# ── Jira ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def jira_creds(monkeypatch):
    async def fake_get_credential_data(credential_id, db):
        return {"domain": "fake.atlassian.net", "email": "me@example.com", "api_token": "faketoken"}
    monkeypatch.setattr("integrations.jira_.handler.get_credential_data", fake_get_credential_data)


@pytest.mark.asyncio
@respx.mock
async def test_jira_create_issue(jira_creds):
    respx.post("https://fake.atlassian.net/rest/api/3/issue").mock(
        return_value=httpx.Response(201, json={"key": "ENG-1", "id": "10001"})
    )
    result = await jira_create_issue(
        {"project_key": "ENG", "summary": "Test issue", "description": "Some details"}, {}, "cred1", FakeDB()
    )
    assert result == {"key": "ENG-1", "id": "10001"}

    # Confirm the description got wrapped in Atlassian Document Format,
    # not sent as a plain string (a real, easy-to-get-wrong detail of
    # Jira Cloud's v3 API).
    import json
    payload = json.loads(respx.calls.last.request.content)
    assert payload["fields"]["description"]["type"] == "doc"


@pytest.mark.asyncio
@respx.mock
async def test_jira_search_issues(jira_creds):
    respx.get("https://fake.atlassian.net/rest/api/3/search").mock(
        return_value=httpx.Response(200, json={
            "total": 1,
            "issues": [{"key": "ENG-2", "fields": {"summary": "Bug", "status": {"name": "Open"}}}],
        })
    )
    result = await jira_search_issues({"jql": "project = ENG"}, {}, "cred1", FakeDB())
    assert result["total"] == 1
    assert result["issues"][0]["key"] == "ENG-2"


@pytest.mark.asyncio
async def test_jira_search_requires_jql(jira_creds):
    with pytest.raises(ValueError, match="jql"):
        await jira_search_issues({}, {}, "cred1", FakeDB())


@pytest.mark.asyncio
@respx.mock
async def test_jira_add_comment(jira_creds):
    respx.post("https://fake.atlassian.net/rest/api/3/issue/ENG-1/comment").mock(
        return_value=httpx.Response(201, json={"id": "10050"})
    )
    result = await jira_add_comment({"issue_key": "ENG-1", "comment": "Looks good"}, {}, "cred1", FakeDB())
    assert result == {"id": "10050"}
