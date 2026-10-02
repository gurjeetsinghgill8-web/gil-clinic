"""Create queue schema and queue_entries table.

Revision ID: 003
Revises: 002
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = ("queue",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create queue schema
    op.execute("CREATE SCHEMA IF NOT EXISTS queue")

    # Create queue_entries table
    op.create_table(
        "queue_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visit_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(30), nullable=False),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_name", sa.String(200), nullable=False),
        sa.Column("service_code", sa.String(20), nullable=False),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("room", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="WAITING"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="queue",
    )

    # Create indexes
    op.create_index(
        "idx_queue_visit_id",
        "queue_entries",
        ["visit_id"],
        schema="queue",
    )
    op.create_index(
        "idx_queue_patient_uuid",
        "queue_entries",
        ["patient_uuid"],
        schema="queue",
    )
    op.create_index(
        "idx_queue_department_status",
        "queue_entries",
        ["department", "status"],
        schema="queue",
    )
    op.create_index(
        "idx_queue_service_token",
        "queue_entries",
        ["service_code", "token_number"],
        schema="queue",
    )
    op.create_index(
        "idx_queue_created_at",
        "queue_entries",
        ["created_at"],
        schema="queue",
    )


def downgrade() -> None:
    op.drop_table("queue_entries", schema="queue")
    op.execute("DROP SCHEMA IF EXISTS queue")
