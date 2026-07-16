"""Create queue.audit_log table.

Revision ID: 004
Revises: 003
Create Date: 2026-07-14

Immutable append-only audit log for all queue actions.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = ("queue",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False, server_default="queue_entry"),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("old_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=True),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="queue",
    )

    # Indexes for fast lookup
    op.create_index(
        "idx_audit_resource",
        "audit_log",
        ["resource_type", "resource_id"],
        schema="queue",
    )
    op.create_index(
        "idx_audit_actor",
        "audit_log",
        ["actor"],
        schema="queue",
    )
    op.create_index(
        "idx_audit_created",
        "audit_log",
        ["created_at"],
        schema="queue",
    )


def downgrade() -> None:
    op.drop_table("audit_log", schema="queue")
