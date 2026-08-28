"""add memory, vector store, and approval tables

Revision ID: 7dbaf66f9abc
Revises: 9d5a798800b8
Create Date: 2026-07-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = '7dbaf66f9abc'
down_revision: Union[str, None] = '9d5a798800b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'memory_messages',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('workflow_id', UUID(as_uuid=False), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_memory_workflow_conversation', 'memory_messages', ['workflow_id', 'conversation_id', 'created_at'])

    op.create_table(
        'vector_documents',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('workflow_id', UUID(as_uuid=False), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('collection', sa.String(length=255), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('doc_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_vector_workflow_collection', 'vector_documents', ['workflow_id', 'collection'])

    # status is a plain string (not a native Postgres enum type) — avoids
    # CREATE TYPE lifecycle complications across repeated migration
    # runs/rollbacks; validated at the application layer instead
    # (storage/models.py's ApprovalStatus Python enum).
    op.create_table(
        'approvals',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('execution_id', UUID(as_uuid=False), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('decided_by', UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_approvals_execution', 'approvals', ['execution_id'])
    op.create_index('ix_approvals_status', 'approvals', ['status'])


def downgrade() -> None:
    op.drop_index('ix_approvals_status', table_name='approvals')
    op.drop_index('ix_approvals_execution', table_name='approvals')
    op.drop_table('approvals')

    op.drop_index('ix_vector_workflow_collection', table_name='vector_documents')
    op.drop_table('vector_documents')

    op.drop_index('ix_memory_workflow_conversation', table_name='memory_messages')
    op.drop_table('memory_messages')
