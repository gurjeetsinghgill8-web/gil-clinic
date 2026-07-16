"""Add pending_alert and alert_message columns to queue_entries.

Adds alert system support for technician-to-patient browser notifications.

Revision ID: 005
Revises: 004
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = ("queue",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "queue_entries",
        sa.Column("pending_alert", sa.Boolean(), nullable=False, server_default="0"),
        schema="queue",
    )
    op.add_column(
        "queue_entries",
        sa.Column("alert_message", sa.String(500), nullable=True),
        schema="queue",
    )


def downgrade() -> None:
    op.drop_column("queue_entries", "pending_alert", schema="queue")
    op.drop_column("queue_entries", "alert_message", schema="queue")
