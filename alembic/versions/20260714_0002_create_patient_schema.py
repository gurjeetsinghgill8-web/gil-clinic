"""Create patient schema and patients table.

Revision ID: 002
Revises: 001
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = ("patient",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create patient schema
    op.execute("CREATE SCHEMA IF NOT EXISTS patient")

    # Create patients table
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("blood_group", sa.String(5), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("phone_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("emergency_contact", postgresql.JSONB(), nullable=True),
        sa.Column("qr_hash", sa.String(64), nullable=True),
        sa.Column("qr_identity", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("registered_devices", postgresql.JSONB(), nullable=True),
        sa.Column("notification_preferences", postgresql.JSONB(), nullable=True),
        sa.Column("medical_history", postgresql.JSONB(), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merged_into_patient_id", sa.String(30), nullable=True),
        sa.Column("reception_inquiry", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        schema="patient",
    )

    # Create indexes
    op.create_index(
        "idx_patients_patient_id",
        "patients",
        ["patient_id"],
        unique=True,
        schema="patient",
    )
    op.create_index(
        "idx_patients_phone_hash",
        "patients",
        ["phone_hash"],
        schema="patient",
    )
    op.create_index(
        "idx_patients_qr_hash",
        "patients",
        ["qr_hash"],
        schema="patient",
    )
    op.create_index(
        "idx_patients_name",
        "patients",
        ["name"],
        schema="patient",
    )
    op.create_index(
        "idx_patients_status",
        "patients",
        ["status"],
        schema="patient",
    )


def downgrade() -> None:
    op.drop_table("patients", schema="patient")
    op.execute("DROP SCHEMA IF EXISTS patient")
