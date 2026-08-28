"""
Seed official starter templates into the marketplace.

These are real, usable workflow definitions built from AutoFlow's actual
node catalog (frontend/src/types/nodes.ts) — not placeholder JSON. A
person installing one gets an editable workflow with the right nodes
wired together; they still need to plug in their own credentials and
adjust things like channel names/repo names to their own setup (that's
inherent to any template, n8n's included), but the structure and node
config are real and correct against the current node catalog.

This does NOT fabricate "thousands of community templates" — see
PRODUCTION_CHECKLIST.md's honest take on this: a marketplace's real value
comes from real users publishing real solutions over time, which no
seed script can substitute for. This is the initial shelf, not the whole
store.

Usage:
    python -m scripts.seed_marketplace_templates
"""
import asyncio

from storage.database import db_context
from core.marketplace import publish_item


def _node(id, type, label, config=None, credential_id=None, position=None):
    n = {"id": id, "type": type, "label": label, "config": config or {}}
    if credential_id:
        n["credential_id"] = credential_id
    if position:
        n["position"] = position
    return n


def _edge(source, target):
    return {"source": source, "target": target}


TEMPLATES = [
    {
        "name": "Slack Notification on Webhook",
        "description": "Receive any HTTP webhook and post a formatted message to a Slack channel. Great starting point for alerting from any external system that can fire a webhook.",
        "category": "Notifications",
        "tags": ["slack", "webhook", "alerting"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "Incoming Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("slack1", "slack.send_message", "Notify Slack", {
                    "channel": "#alerts",
                    "text": "New event received:\n```{{ trigger.body }}```",
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "slack1")],
        },
    },
    {
        "name": "GitHub Issue → Notion Tracker",
        "description": "Whenever a new GitHub issue is opened (via webhook), create a matching page in a Notion database so product/support can triage without needing GitHub access.",
        "category": "Dev Tools",
        "tags": ["github", "notion", "issue-tracking"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "GitHub Issue Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("notion1", "notion.create_page", "Log to Notion", {
                    "parent_type": "database_id",
                    "properties": {
                        "Title": "{{ trigger.body.issue.title }}",
                        "URL": "{{ trigger.body.issue.html_url }}",
                        "Reporter": "{{ trigger.body.issue.user.login }}",
                    },
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "notion1")],
        },
    },
    {
        "name": "Daily Database Report to Slack",
        "description": "Runs every weekday morning, queries your database for a summary row count, and posts it to Slack. Swap the SQL for whatever metric matters to your team.",
        "category": "Reporting",
        "tags": ["database", "slack", "schedule", "reporting"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.schedule", "Every Weekday 9am", {"cron_expression": "0 9 * * 1-5", "timezone": "UTC"}, position={"x": 0, "y": 0}),
                _node("db1", "database.query", "Count New Signups", {
                    "query": "SELECT COUNT(*) AS new_signups FROM users WHERE created_at >= NOW() - INTERVAL '1 day'",
                    "max_rows": 10,
                }, position={"x": 280, "y": 0}),
                _node("slack1", "slack.send_message", "Post Report", {
                    "channel": "#daily-metrics",
                    "text": "Yesterday's new signups: {{ nodes.db1.rows.0.new_signups }}",
                }, position={"x": 560, "y": 0}),
            ],
            "edges": [_edge("trigger1", "db1"), _edge("db1", "slack1")],
        },
    },
    {
        "name": "New HubSpot Contact → Google Sheet Log",
        "description": "Every time a new contact is created in HubSpot (via webhook), append a row to a Google Sheet — a simple audit trail without needing HubSpot report-building access.",
        "category": "CRM",
        "tags": ["hubspot", "sheets", "crm"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "HubSpot Contact Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("sheets1", "sheets.append_row", "Log to Sheet", {
                    "spreadsheet_id": "YOUR_SPREADSHEET_ID",
                    "sheet_name": "Contacts",
                    "values": {"email": "{{ trigger.body.email }}", "name": "{{ trigger.body.firstname }} {{ trigger.body.lastname }}"},
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "sheets1")],
        },
    },
    {
        "name": "WhatsApp Order Confirmation",
        "description": "Receives an order webhook (from your store/checkout system) and sends the customer a WhatsApp confirmation message automatically.",
        "category": "E-commerce",
        "tags": ["whatsapp", "orders", "e-commerce"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "Order Placed Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("wa1", "whatsapp.send_text", "Send Confirmation", {
                    "to": "{{ trigger.body.customer_phone }}",
                    "text": "Hi {{ trigger.body.customer_name }}! Your order #{{ trigger.body.order_id }} is confirmed. Thanks for shopping with us.",
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "wa1")],
        },
    },
    {
        "name": "Airtable ↔ Slack Record Sync",
        "description": "On a schedule, pull recently updated Airtable records and post a Slack digest — useful for teams that live in Airtable but want visibility in Slack without checking the base directly.",
        "category": "Productivity",
        "tags": ["airtable", "slack", "sync"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.schedule", "Every Hour", {"cron_expression": "0 * * * *", "timezone": "UTC"}, position={"x": 0, "y": 0}),
                _node("airtable1", "airtable.list_records", "Get Recent Records", {
                    "base_id": "YOUR_BASE_ID", "table_name": "Tasks", "max_records": 10,
                }, position={"x": 280, "y": 0}),
                _node("slack1", "slack.send_message", "Post Digest", {
                    "channel": "#airtable-updates",
                    "text": "Recent Airtable updates:\n{{ nodes.airtable1.records }}",
                }, position={"x": 560, "y": 0}),
            ],
            "edges": [_edge("trigger1", "airtable1"), _edge("airtable1", "slack1")],
        },
    },
    {
        "name": "HTTP Health Check Monitor",
        "description": "Pings a URL on a schedule; if the response looks unhealthy, alerts Slack. A minimal uptime monitor you fully control, no third-party SaaS needed.",
        "category": "Monitoring",
        "tags": ["http", "monitoring", "uptime", "slack"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.schedule", "Every 5 Minutes", {"cron_expression": "*/5 * * * *", "timezone": "UTC"}, position={"x": 0, "y": 0}),
                _node("http1", "http.request", "Check Endpoint", {
                    "method": "GET", "url": "https://your-service.example.com/health",
                }, position={"x": 280, "y": 0}),
                _node("filter1", "core.filter", "Only If Unhealthy", {
                    "field": "{{ nodes.http1.status_code }}", "operator": "not_equals", "value": "200",
                }, position={"x": 560, "y": 0}),
                _node("slack1", "slack.send_message", "Alert Slack", {
                    "channel": "#incidents",
                    "text": ":rotating_light: Health check failed — status {{ nodes.http1.status_code }}",
                }, position={"x": 840, "y": 0}),
            ],
            "edges": [_edge("trigger1", "http1"), _edge("http1", "filter1"), _edge("filter1", "slack1")],
        },
    },
    {
        "name": "New GitHub Release → Discord Announcement",
        "description": "Whenever a GitHub release is published, post an announcement embed to a Discord channel — handy for open-source projects that release often.",
        "category": "Dev Tools",
        "tags": ["github", "discord", "releases"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "GitHub Release Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("discord1", "discord.send_embed", "Announce Release", {
                    "title": "New release: {{ trigger.body.release.tag_name }}",
                    "description": "{{ trigger.body.release.body }}",
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "discord1")],
        },
    },
    {
        "name": "Stripe Payment Failed → Jira Ticket + Email",
        "description": "When a Stripe charge fails (via webhook), automatically open a Jira ticket for billing follow-up and email the customer a payment-retry link.",
        "category": "Billing",
        "tags": ["stripe", "jira", "email", "billing"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "Stripe Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("jira1", "jira.create_issue", "Open Billing Ticket", {
                    "project_key": "BILL", "issue_type": "Task",
                    "summary": "Failed charge for {{ trigger.body.data.object.customer }}",
                    "description": "Charge {{ trigger.body.data.object.id }} failed. Amount: {{ trigger.body.data.object.amount }}",
                }, position={"x": 280, "y": 0}),
                _node("email1", "email.send", "Notify Customer", {
                    "to": "{{ trigger.body.data.object.receipt_email }}",
                    "from": "billing@yourcompany.com",
                    "subject": "Payment issue with your recent order",
                    "body": "We had trouble processing your payment. Please update your payment method to keep your account active.",
                }, position={"x": 560, "y": 0}),
            ],
            "edges": [_edge("trigger1", "jira1"), _edge("trigger1", "email1")],
        },
    },
    {
        "name": "New Order → SMS Confirmation",
        "description": "Receives an order webhook and texts the customer a confirmation via Twilio — an SMS-first alternative to the WhatsApp order confirmation template.",
        "category": "E-commerce",
        "tags": ["twilio", "sms", "orders"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "Order Placed Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("sms1", "twilio.send_sms", "Send Confirmation SMS", {
                    "to": "{{ trigger.body.customer_phone }}",
                    "from": "+15550000000",
                    "body": "Hi {{ trigger.body.customer_name }}! Your order #{{ trigger.body.order_id }} is confirmed.",
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "sms1")],
        },
    },
    {
        "name": "Health Check Failure → PagerDuty Incident",
        "description": "Upgrades the HTTP Health Check Monitor template — instead of (or alongside) a Slack ping, open a real PagerDuty incident so it actually pages someone on-call.",
        "category": "Monitoring",
        "tags": ["http", "pagerduty", "monitoring", "on-call"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.schedule", "Every 5 Minutes", {"cron_expression": "*/5 * * * *", "timezone": "UTC"}, position={"x": 0, "y": 0}),
                _node("http1", "http.request", "Check Endpoint", {
                    "method": "GET", "url": "https://your-service.example.com/health",
                }, position={"x": 280, "y": 0}),
                _node("filter1", "core.filter", "Only If Unhealthy", {
                    "field": "{{ nodes.http1.status_code }}", "operator": "not_equals", "value": "200",
                }, position={"x": 560, "y": 0}),
                _node("pd1", "pagerduty.trigger_incident", "Page On-Call", {
                    "summary": "Health check failing — status {{ nodes.http1.status_code }}",
                    "severity": "critical", "source": "autoflow-monitor",
                }, position={"x": 840, "y": 0}),
            ],
            "edges": [_edge("trigger1", "http1"), _edge("http1", "filter1"), _edge("filter1", "pd1")],
        },
    },
    {
        "name": "New Stripe Customer → Asana Onboarding Task",
        "description": "When a new customer signs up in Stripe, automatically create an Asana task for your team to kick off onboarding — never miss a new customer.",
        "category": "CRM",
        "tags": ["stripe", "asana", "onboarding"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.webhook", "Stripe Customer Created Webhook", {"method": "POST"}, position={"x": 0, "y": 0}),
                _node("asana1", "asana.create_task", "Create Onboarding Task", {
                    "project_id": "YOUR_ONBOARDING_PROJECT_ID",
                    "name": "Onboard {{ trigger.body.data.object.email }}",
                    "notes": "New Stripe customer: {{ trigger.body.data.object.id }}",
                }, position={"x": 280, "y": 0}),
            ],
            "edges": [_edge("trigger1", "asana1")],
        },
    },
    {
        "name": "Daily Report → S3 Archive",
        "description": "Runs a database query on a schedule and archives the result as a CSV-shaped text file in S3 — a simple, self-hosted alternative to a BI tool for teams that just need historical snapshots.",
        "category": "Reporting",
        "tags": ["database", "s3", "archive", "reporting"],
        "item_type": "template",
        "content": {
            "nodes": [
                _node("trigger1", "trigger.schedule", "Every Night", {"cron_expression": "0 2 * * *", "timezone": "UTC"}, position={"x": 0, "y": 0}),
                _node("db1", "database.query", "Pull Daily Stats", {
                    "query": "SELECT COUNT(*) AS total_users FROM users",
                    "max_rows": 10,
                }, position={"x": 280, "y": 0}),
                _node("s3_1", "s3.put_object", "Archive to S3", {
                    "bucket": "YOUR_REPORTS_BUCKET",
                    "key": "daily-reports/{{ trigger.body.date }}.json",
                    "body": "{{ nodes.db1.rows }}",
                }, position={"x": 560, "y": 0}),
            ],
            "edges": [_edge("trigger1", "db1"), _edge("db1", "s3_1")],
        },
    },
]


async def seed() -> None:
    created, skipped = 0, 0
    async with db_context() as db:
        for t in TEMPLATES:
            try:
                item = await publish_item(
                    db, org_id=None, name=t["name"], description=t["description"],
                    category=t["category"], tags=t["tags"], item_type=t["item_type"], content=t["content"],
                )
                item.is_verified = True  # official AutoFlow-authored templates, marked as such in the UI
                created += 1
                print(f"  + {item.slug}")
            except ValueError:
                skipped += 1
                print(f"  = {_slugify_preview(t['name'])} already exists, skipping")
        await db.commit()
    print(f"\nSeed complete: {created} created, {skipped} already existed")


def _slugify_preview(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


if __name__ == "__main__":
    asyncio.run(seed())
