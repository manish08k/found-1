"""AutoFlow — FastAPI application entry point."""
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from core.config import settings
from core.telemetry import instrument_app
from storage.database import engine
from storage.models import Base
from schedules.manager import start_scheduler, stop_scheduler
from api.routes import oauth, workflows, executions, credentials, webhooks, triggers, schedules
from api.routes import orgs, versions, dlq, marketplace, privacy, billing, approvals, mcp_server
from api.routes import chat_messages, assistants, document_stores, api_keys, variables, leads, feedback
from api.routes.auth import router as auth_router
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.idempotency import IdempotencyMiddleware

import integrations.core.nodes
import integrations.ai.handler
import integrations.vector.handler
import integrations.slack.handler
import integrations.google.sheets
import integrations.google.gmail
import integrations.google.drive
import integrations.google.calendar
import integrations.whatsapp.handler
import integrations.telegram.handler
import integrations.github.handler
import integrations.notion.handler
import integrations.discord.handler
import integrations.airtable.handler
import integrations.hubspot.handler
import integrations.database.handler
import integrations.stripe_.handler
import integrations.email_.handler
import integrations.twilio_.handler
import integrations.jira_.handler
import integrations.trello_.handler
import integrations.pagerduty_.handler
import integrations.asana_.handler
import integrations.aws_s3_.handler
import integrations.mcp_.handler
# Extended LLM providers
import integrations.llm.handler
# Tool nodes
import integrations.tools.handler
# Document loaders
import integrations.document_loaders.handler
# Text splitters
import integrations.text_splitters.handler
# Agent nodes
import integrations.agents.handler
# New SaaS integrations
import integrations.zendesk.handler
import integrations.linear.handler
import integrations.salesforce.handler
import integrations.confluence.handler
import integrations.zoom.handler
import integrations.monday.handler
import integrations.mailchimp.handler
import integrations.freshdesk.handler
import integrations.intercom.handler
import integrations.typeform.handler
import integrations.box.handler
import integrations.dropbox.handler
# New node integrations (Flowise inventory parity)
import integrations.chains.handler
import integrations.cache.handler
import integrations.memory.handler
import integrations.outputparsers.handler
import integrations.prompts.handler
import integrations.retrievers.handler
import integrations.vectorstores.handler
import integrations.analytic.handler
import integrations.speechtotext.handler
import integrations.graphs.handler
import integrations.recordmanager.handler
import integrations.embeddings.handler
# New Flowise parity integrations
import integrations.agentflow.handler
import integrations.engine.handler
import integrations.moderation.handler
import integrations.responsesynthesizer.handler
import integrations.sequentialagents.handler
import integrations.utilities.handler

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await start_scheduler()
    log.info("autoflow_started", env=settings.APP_ENV)
    yield
    await stop_scheduler()
    await engine.dispose()
    log.info("autoflow_stopped")


app = FastAPI(
    title="AutoFlow",
    description="Production-grade workflow automation platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [settings.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

instrument_app(app)

app.include_router(auth_router)
app.include_router(oauth.router,       prefix="/oauth",           tags=["OAuth"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["Credentials"])
app.include_router(workflows.router,   prefix="/api/workflows",   tags=["Workflows"])
app.include_router(versions.router,    prefix="/api/workflows",   tags=["Workflow Versioning"])
app.include_router(executions.router,  prefix="/api/executions",  tags=["Executions"])
app.include_router(triggers.router,    prefix="/api/triggers",    tags=["Triggers"])
app.include_router(schedules.router,   prefix="/api/schedules",   tags=["Schedules"])
app.include_router(webhooks.router,    prefix="/webhooks",        tags=["Webhooks"])
app.include_router(orgs.router,        prefix="/api/orgs",        tags=["Organizations"])
app.include_router(dlq.router,         prefix="/api/dlq",         tags=["Dead Letter Queue"])
app.include_router(marketplace.router, prefix="/api/marketplace", tags=["Marketplace"])
app.include_router(privacy.router)
app.include_router(billing.router)
app.include_router(approvals.router)
app.include_router(mcp_server.router)
app.include_router(chat_messages.router, prefix="/api/chat-messages",   tags=["Chat Messages"])
app.include_router(assistants.router,    prefix="/api/assistants",      tags=["Assistants"])
app.include_router(document_stores.router, prefix="/api/document-stores", tags=["Document Stores"])
app.include_router(api_keys.router,      prefix="/api/api-keys",        tags=["API Keys"])
app.include_router(variables.router,     prefix="/api/variables",       tags=["Variables"])
app.include_router(leads.router,         prefix="/api/leads",           tags=["Leads"])
app.include_router(feedback.router,      prefix="/api/feedback",        tags=["Feedback"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/api/providers", tags=["OAuth"])
async def list_providers(response: Response):
    # Static per-deploy (the provider list only changes when code changes,
    # never per-request or per-user) — safe to cache at the edge/browser.
    response.headers["Cache-Control"] = "public, max-age=300"
    from oauth.providers import PROVIDERS
    return {"providers": [
        {"name": p.name, "display_name": p.display_name,
         "icon": p.icon, "scopes": p.default_scopes}
        for p in PROVIDERS.values()
    ]}


@app.get("/api/node-types", tags=["Workflows"])
async def list_node_types(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    from core.execution_engine import NODE_HANDLERS
    return {"node_types": sorted(NODE_HANDLERS.keys())}