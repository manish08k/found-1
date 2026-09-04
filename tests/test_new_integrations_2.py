"""
Tests for newly added integrations: WooCommerce, Webex, RingCentral.

All external HTTP calls are mocked with respx so no live credentials are needed.
"""
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

# ── WooCommerce ───────────────────────────────────────────────────────────────
from integrations.woocommerce.handler import (
    woocommerce_list_orders,
    woocommerce_get_order,
    woocommerce_update_order,
    woocommerce_create_order,
    woocommerce_list_products,
    woocommerce_get_product,
    woocommerce_create_product,
    woocommerce_update_product,
    woocommerce_list_customers,
    woocommerce_create_customer,
    woocommerce_get_sales_report,
    woocommerce_get_system_status,
)

# ── Webex ─────────────────────────────────────────────────────────────────────
from integrations.webex.handler import (
    webex_send_message,
    webex_list_rooms,
    webex_create_room,
    webex_list_messages,
    webex_get_me,
    webex_list_people,
    webex_create_meeting,
)

# ── RingCentral ───────────────────────────────────────────────────────────────
from integrations.ringcentral.handler import (
    ringcentral_send_sms,
    ringcentral_list_messages,
    ringcentral_get_call_log,
    ringcentral_make_call,
    ringcentral_list_extensions,
    ringcentral_get_account_info,
)

DB = AsyncMock()
CRED = "test-cred-id"

WC_CREDS = {
    "store_url": "https://mystore.example.com",
    "consumer_key": "ck_test",
    "consumer_secret": "cs_test",
}
WEBEX_CREDS = {"access_token": "webex-test-token"}
RC_CREDS = {"access_token": "rc-test-token"}


# =============================================================================
# WooCommerce Tests
# =============================================================================

@pytest.mark.asyncio
class TestWooCommerceOrders:
    @respx.mock
    async def test_list_orders(self):
        respx.get("https://mystore.example.com/wc/v3/orders").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "status": "processing"}])
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_list_orders(
                config={"status": "processing", "per_page": 5},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["orders"][0]["id"] == 1

    @respx.mock
    async def test_get_order(self):
        respx.get("https://mystore.example.com/wc/v3/orders/42").mock(
            return_value=httpx.Response(200, json={"id": 42, "status": "completed"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_get_order(
                config={"order_id": "42"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["order"]["id"] == 42

    @respx.mock
    async def test_update_order(self):
        respx.put("https://mystore.example.com/wc/v3/orders/42").mock(
            return_value=httpx.Response(200, json={"id": 42, "status": "completed"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_update_order(
                config={"order_id": "42", "status": "completed"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["order"]["status"] == "completed"

    @respx.mock
    async def test_create_order(self):
        respx.post("https://mystore.example.com/wc/v3/orders").mock(
            return_value=httpx.Response(201, json={"id": 99, "status": "pending"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_create_order(
                config={"order": {"line_items": [{"product_id": 1, "quantity": 2}]}},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["order"]["id"] == 99

    async def test_get_order_missing_id(self):
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            with pytest.raises(ValueError, match="requires 'order_id'"):
                await woocommerce_get_order(
                    config={}, input_data={}, credential_id=CRED, db=DB
                )


@pytest.mark.asyncio
class TestWooCommerceProducts:
    @respx.mock
    async def test_list_products(self):
        respx.get("https://mystore.example.com/wc/v3/products").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "name": "T-Shirt"}])
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_list_products(
                config={"per_page": 5},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["products"][0]["name"] == "T-Shirt"

    @respx.mock
    async def test_get_product(self):
        respx.get("https://mystore.example.com/wc/v3/products/7").mock(
            return_value=httpx.Response(200, json={"id": 7, "name": "Hoodie"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_get_product(
                config={"product_id": "7"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["product"]["name"] == "Hoodie"

    @respx.mock
    async def test_create_product(self):
        respx.post("https://mystore.example.com/wc/v3/products").mock(
            return_value=httpx.Response(201, json={"id": 50, "name": "New Product"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_create_product(
                config={"product": {"name": "New Product", "regular_price": "9.99", "type": "simple"}},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["product"]["id"] == 50

    @respx.mock
    async def test_update_product(self):
        respx.put("https://mystore.example.com/wc/v3/products/7").mock(
            return_value=httpx.Response(200, json={"id": 7, "regular_price": "19.99"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_update_product(
                config={"product_id": "7", "regular_price": "19.99"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["product"]["regular_price"] == "19.99"


@pytest.mark.asyncio
class TestWooCommerceCustomers:
    @respx.mock
    async def test_list_customers(self):
        respx.get("https://mystore.example.com/wc/v3/customers").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "email": "user@example.com"}])
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_list_customers(
                config={"per_page": 10},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["customers"][0]["email"] == "user@example.com"

    @respx.mock
    async def test_create_customer(self):
        respx.post("https://mystore.example.com/wc/v3/customers").mock(
            return_value=httpx.Response(201, json={"id": 5, "email": "new@example.com"})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_create_customer(
                config={"email": "new@example.com", "first_name": "Jane"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["customer"]["id"] == 5

    async def test_create_customer_missing_email(self):
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            with pytest.raises(ValueError, match="requires 'email'"):
                await woocommerce_create_customer(
                    config={}, input_data={}, credential_id=CRED, db=DB
                )


@pytest.mark.asyncio
class TestWooCommerceReports:
    @respx.mock
    async def test_get_sales_report(self):
        respx.get("https://mystore.example.com/wc/v3/reports/sales").mock(
            return_value=httpx.Response(200, json=[{"total_sales": "1000.00", "total_orders": 10}])
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_get_sales_report(
                config={"period": "month"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["report"][0]["total_orders"] == 10

    @respx.mock
    async def test_get_system_status(self):
        respx.get("https://mystore.example.com/wc/v3/system_status").mock(
            return_value=httpx.Response(200, json={"environment": {"wc_version": "9.0.0"}})
        )
        with patch("integrations.woocommerce.handler.get_credential_data", return_value=WC_CREDS):
            result = await woocommerce_get_system_status(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert "environment" in result["system_status"]


# =============================================================================
# Webex Tests
# =============================================================================

@pytest.mark.asyncio
class TestWebexMessages:
    @respx.mock
    async def test_send_message_to_room(self):
        respx.post("https://webexapis.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg-1", "text": "Hello!"})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_send_message(
                config={"roomId": "room-abc", "text": "Hello!"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["message"]["id"] == "msg-1"

    @respx.mock
    async def test_send_message_to_person(self):
        respx.post("https://webexapis.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg-2", "text": "Hi"})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_send_message(
                config={"toPersonEmail": "user@example.com", "text": "Hi"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["message"]["id"] == "msg-2"

    async def test_send_message_missing_destination(self):
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            with pytest.raises(ValueError, match="requires 'roomId'"):
                await webex_send_message(
                    config={"text": "Hello"}, input_data={}, credential_id=CRED, db=DB
                )

    async def test_send_message_missing_content(self):
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            with pytest.raises(ValueError, match="requires 'text'"):
                await webex_send_message(
                    config={"roomId": "room-x"}, input_data={}, credential_id=CRED, db=DB
                )

    @respx.mock
    async def test_list_messages(self):
        respx.get("https://webexapis.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "m1", "text": "Hi"}]})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_list_messages(
                config={"roomId": "room-x", "max": 10},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["items"][0]["id"] == "m1"


@pytest.mark.asyncio
class TestWebexRooms:
    @respx.mock
    async def test_list_rooms(self):
        respx.get("https://webexapis.com/v1/rooms").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "room-1", "title": "General"}]})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_list_rooms(
                config={"max": 20},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["items"][0]["title"] == "General"

    @respx.mock
    async def test_create_room(self):
        respx.post("https://webexapis.com/v1/rooms").mock(
            return_value=httpx.Response(200, json={"id": "new-room", "title": "New Space"})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_create_room(
                config={"title": "New Space"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["room"]["title"] == "New Space"


@pytest.mark.asyncio
class TestWebexPeople:
    @respx.mock
    async def test_get_me(self):
        respx.get("https://webexapis.com/v1/people/me").mock(
            return_value=httpx.Response(200, json={"id": "me-id", "displayName": "Test User"})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_get_me(
                config={}, input_data={}, credential_id=CRED, db=DB
            )
        assert result["person"]["displayName"] == "Test User"

    @respx.mock
    async def test_list_people(self):
        respx.get("https://webexapis.com/v1/people").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "p1", "email": "a@b.com"}]})
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_list_people(
                config={"email": "a@b.com"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["items"][0]["email"] == "a@b.com"


@pytest.mark.asyncio
class TestWebexMeetings:
    @respx.mock
    async def test_create_meeting(self):
        respx.post("https://webexapis.com/v1/meetings").mock(
            return_value=httpx.Response(200, json={
                "id": "meet-1",
                "title": "Sprint Review",
                "start": "2026-09-10T10:00:00Z",
                "end": "2026-09-10T11:00:00Z",
            })
        )
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            result = await webex_create_meeting(
                config={
                    "title": "Sprint Review",
                    "start": "2026-09-10T10:00:00Z",
                    "end": "2026-09-10T11:00:00Z",
                },
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["meeting"]["id"] == "meet-1"

    async def test_create_meeting_missing_fields(self):
        with patch("integrations.webex.handler.get_credential_data", return_value=WEBEX_CREDS):
            with pytest.raises(ValueError, match="requires 'title'"):
                await webex_create_meeting(
                    config={}, input_data={}, credential_id=CRED, db=DB
                )


# =============================================================================
# RingCentral Tests
# =============================================================================

@pytest.mark.asyncio
class TestRingCentralSMS:
    @respx.mock
    async def test_send_sms(self):
        respx.post("https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/sms").mock(
            return_value=httpx.Response(200, json={"id": "sms-123", "type": "SMS"})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_send_sms(
                config={
                    "from": "+14155551234",
                    "to": "+19999999999",
                    "text": "Hello from AutoFlow!",
                },
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["message"]["id"] == "sms-123"

    async def test_send_sms_missing_from(self):
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            with pytest.raises(ValueError, match="requires 'from'"):
                await ringcentral_send_sms(
                    config={"to": "+19999999999", "text": "Hi"},
                    input_data={},
                    credential_id=CRED,
                    db=DB,
                )

    @respx.mock
    async def test_list_messages(self):
        respx.get(
            "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/message-store"
        ).mock(
            return_value=httpx.Response(200, json={"records": [{"id": "m1", "type": "SMS"}]})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_list_messages(
                config={"messageType": "SMS"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["records"][0]["id"] == "m1"


@pytest.mark.asyncio
class TestRingCentralCallLog:
    @respx.mock
    async def test_get_call_log(self):
        respx.get(
            "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
        ).mock(
            return_value=httpx.Response(200, json={"records": [{"id": "c1", "direction": "Inbound"}]})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_get_call_log(
                config={"direction": "Inbound"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["records"][0]["direction"] == "Inbound"


@pytest.mark.asyncio
class TestRingCentralCallMaking:
    @respx.mock
    async def test_make_call(self):
        respx.post(
            "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/ring-out"
        ).mock(
            return_value=httpx.Response(200, json={"id": "call-1", "status": {"callStatus": "InProgress"}})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_make_call(
                config={"from": "+14155551234", "to": "+19999999999"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["call"]["id"] == "call-1"

    async def test_make_call_missing_from(self):
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            with pytest.raises(ValueError, match="requires 'from' and 'to'"):
                await ringcentral_make_call(
                    config={"to": "+19999999999"},
                    input_data={},
                    credential_id=CRED,
                    db=DB,
                )


@pytest.mark.asyncio
class TestRingCentralAccount:
    @respx.mock
    async def test_list_extensions(self):
        respx.get(
            "https://platform.ringcentral.com/restapi/v1.0/account/~/extension"
        ).mock(
            return_value=httpx.Response(200, json={"records": [{"id": "ext-1", "status": "Enabled"}]})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_list_extensions(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["records"][0]["id"] == "ext-1"

    @respx.mock
    async def test_get_account_info(self):
        respx.get(
            "https://platform.ringcentral.com/restapi/v1.0/account/~"
        ).mock(
            return_value=httpx.Response(200, json={"id": "~", "serviceInfo": {"brand": {"name": "RingCentral"}}})
        )
        with patch("integrations.ringcentral.handler.get_credential_data", return_value=RC_CREDS):
            result = await ringcentral_get_account_info(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert result["account"]["id"] == "~"
