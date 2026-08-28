"""Add assistants, document_stores, api_keys, variables, leads, message_feedback tables

Revision ID: e3f9a1b2c4d5
Revises: d13d7b0ccf19
Create Date: 2026-08-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f9a1b2c4d5"
down_revision = "d13d7b0ccf19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── assistants ──────────────────────────────────────────────────────────
    op.create_table(
        "assistants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, default="You are a helpful assistant."),
        sa.Column("model", sa.String(128), default="gpt-4o-mini"),
        sa.Column("provider", sa.String(64), default="openai"),
        sa.Column("tools", sa.JSON, default=list),
        sa.Column("temperature", sa.Integer, default=7),
        sa.Column("max_tokens", sa.Integer, default=1024),
        sa.Column("document_store_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_assistant_owner", "assistants", ["owner_id"])

    # ── assistant_threads ────────────────────────────────────────────────────
    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assistant_id", sa.String(36), sa.ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_thread_assistant", "assistant_threads", ["assistant_id"])

    # ── assistant_messages ───────────────────────────────────────────────────
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("assistant_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_asst_msg_thread", "assistant_messages", ["thread_id"])

    # ── document_stores ──────────────────────────────────────────────────────
    op.create_table(
        "document_stores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("embedding_model", sa.String(128), default="text-embedding-3-small"),
        sa.Column("embedding_provider", sa.String(64), default="openai"),
        sa.Column("chunk_size", sa.Integer, default=1000),
        sa.Column("chunk_overlap", sa.Integer, default=200),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_docstore_owner", "document_stores", ["owner_id"])

    # ── api_keys ─────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("revoked", sa.Boolean, default=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_apikey_hash", "api_keys", ["key_hash"])
    op.create_index("ix_apikey_user", "api_keys", ["user_id", "revoked"])

    # ── variables ────────────────────────────────────────────────────────────
    op.create_table(
        "variables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_secret", sa.Boolean, default=False),
        sa.Column("variable_type", sa.String(32), default="string"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_variable_owner", "variables", ["owner_id"])
    op.create_unique_constraint("uq_variable_owner_name", "variables", ["owner_id", "name"])

    # ── leads ────────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("conversation_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), default="new"),
        sa.Column("lead_metadata", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_lead_owner", "leads", ["owner_id"])
    op.create_index("ix_lead_workflow", "leads", ["workflow_id"])

    # ── message_feedback ─────────────────────────────────────────────────────
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("conversation_id", sa.String(255), nullable=True),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_feedback_workflow", "message_feedback", ["workflow_id"])
    op.create_index("ix_feedback_message", "message_feedback", ["message_id"])


def downgrade() -> None:
    op.drop_table("message_feedback")
    op.drop_table("leads")
    op.drop_table("variables")
    op.drop_table("api_keys")
    op.drop_table("document_stores")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_threads")
    op.drop_table("assistants")
