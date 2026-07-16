"""Initial identity schema — all 7 tables in identity schema.

Revision ID: 001
Revises: None
Create Date: 2026-07-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = ("identity",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the identity schema and all 7 tables."""

    # Create identity schema
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")

    # =========================================================================
    # Table: identity.roles
    # =========================================================================
    op.create_table(
        "roles",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hierarchy_level BETWEEN 0 AND 100",
            name="ck_roles_hierarchy_level_range",
        ),
        schema="identity",
    )

    # =========================================================================
    # Table: identity.users
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column(
            "full_name",
            sa.String(512),
            nullable=False,
            comment="AES-256-GCM encrypted at application layer",
        ),
        sa.Column(
            "role_code",
            sa.String(20),
            sa.ForeignKey("identity.roles.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("pin_hash", sa.String(255), nullable=True),
        sa.Column(
            "phone",
            sa.String(512),
            nullable=False,
            comment="AES-256-GCM encrypted at application layer",
        ),
        sa.Column(
            "phone_hash",
            sa.String(64),
            unique=True,
            nullable=False,
            comment="SHA-256 hash for lookup queries on encrypted phone",
        ),
        sa.Column(
            "email",
            sa.String(512),
            nullable=True,
            comment="AES-256-GCM encrypted at application layer",
        ),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
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
        # CHECK constraints
        sa.CheckConstraint(
            "login_attempts >= 0",
            name="ck_users_login_attempts_positive",
        ),
        schema="identity",
    )

    # Indexes for users
    op.create_index("idx_users_role", "users", ["role_code"], schema="identity")
    op.create_index("idx_users_department", "users", ["department"], schema="identity")
    op.create_index("idx_users_phone_hash", "users", ["phone_hash"], schema="identity")
    op.create_index(
        "idx_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
        schema="identity",
    )

    # =========================================================================
    # Table: identity.user_sessions
    # =========================================================================
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "last_activity",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_trusted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )

    op.create_index(
        "idx_sessions_user", "user_sessions", ["user_id"], schema="identity"
    )
    op.create_index(
        "idx_sessions_active",
        "user_sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
        schema="identity",
    )

    # =========================================================================
    # Table: identity.refresh_tokens
    # =========================================================================
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.user_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )

    op.create_index(
        "idx_refresh_user", "refresh_tokens", ["user_id"], schema="identity"
    )
    op.create_index(
        "idx_refresh_hash", "refresh_tokens", ["token_hash"], schema="identity"
    )
    op.create_index(
        "idx_refresh_active",
        "refresh_tokens",
        ["user_id"],
        postgresql_where=sa.text("is_revoked = false"),
        schema="identity",
    )

    # =========================================================================
    # Table: identity.otp_codes
    # =========================================================================
    op.create_table(
        "otp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 5",
            name="ck_otp_codes_attempts_range",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="identity",
    )

    op.create_index("idx_otp_user", "otp_codes", ["user_id"], schema="identity")
    op.create_index("idx_otp_expired", "otp_codes", ["expires_at"], schema="identity")

    # =========================================================================
    # Table: identity.permissions
    # =========================================================================
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "role_code",
            sa.String(20),
            sa.ForeignKey("identity.roles.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("is_granted", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "role_code", "resource", "action",
            name="uq_permission_role_resource_action",
        ),
        schema="identity",
    )

    # =========================================================================
    # Table: identity.outbox
    # =========================================================================
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )

    op.create_index(
        "idx_outbox_status_created",
        "outbox",
        ["status", "created_at"],
        schema="identity",
    )
    op.create_index(
        "idx_outbox_pending",
        "outbox",
        ["created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
        schema="identity",
    )

    # =========================================================================
    # Seed Data: Default Roles
    # =========================================================================
    op.execute(
        """
        INSERT INTO identity.roles (code, name, hierarchy_level, description) VALUES
            ('ADMIN', 'Administrator', 100, 'Full system access'),
            ('MANAGER', 'Manager', 80, 'Operational management'),
            ('DOCTOR', 'Doctor', 60, 'Clinical consultation'),
            ('NURSE', 'Nurse', 50, 'Patient care support'),
            ('RECEPTIONIST', 'Receptionist', 40, 'Front desk operations'),
            ('TECHNICIAN', 'Technician', 40, 'Test/lab operations'),
            ('PHARMACIST', 'Pharmacist', 40, 'Pharmacy operations'),
            ('LAB_TECH', 'Lab Technician', 40, 'Lab sample processing'),
            ('RADIOLOGIST', 'Radiologist', 40, 'Imaging operations')
        """
    )

    # =========================================================================
    # Seed Data: Default Permissions for each role
    # =========================================================================
    op.execute(
        """
        INSERT INTO identity.permissions (id, role_code, resource, action, is_granted) VALUES

            -- Admin: everything
            (gen_random_uuid(), 'ADMIN', '*', '*', true),

            -- Receptionist: patient registration + queue management
            (gen_random_uuid(), 'RECEPTIONIST', 'patients', 'read', true),
            (gen_random_uuid(), 'RECEPTIONIST', 'patients', 'write', true),
            (gen_random_uuid(), 'RECEPTIONIST', 'queue', 'read', true),
            (gen_random_uuid(), 'RECEPTIONIST', 'queue', 'write', true),
            (gen_random_uuid(), 'RECEPTIONIST', 'appointments', 'read', true),
            (gen_random_uuid(), 'RECEPTIONIST', 'appointments', 'write', true),

            -- Doctor: clinical read/write
            (gen_random_uuid(), 'DOCTOR', 'patients', 'read', true),
            (gen_random_uuid(), 'DOCTOR', 'patients', 'write', true),
            (gen_random_uuid(), 'DOCTOR', 'queue', 'read', true),
            (gen_random_uuid(), 'DOCTOR', 'prescriptions', 'write', true),
            (gen_random_uuid(), 'DOCTOR', 'clinical_notes', 'write', true),
            (gen_random_uuid(), 'DOCTOR', 'lab_reports', 'read', true),
            (gen_random_uuid(), 'DOCTOR', 'radiology_reports', 'read', true),

            -- Technician: test operations
            (gen_random_uuid(), 'TECHNICIAN', 'patients', 'read', true),
            (gen_random_uuid(), 'TECHNICIAN', 'tests', 'read', true),
            (gen_random_uuid(), 'TECHNICIAN', 'tests', 'write', true),
            (gen_random_uuid(), 'TECHNICIAN', 'queue', 'read', true),

            -- Nurse: patient vitals
            (gen_random_uuid(), 'NURSE', 'patients', 'read', true),
            (gen_random_uuid(), 'NURSE', 'vitals', 'read', true),
            (gen_random_uuid(), 'NURSE', 'vitals', 'write', true),
            (gen_random_uuid(), 'NURSE', 'queue', 'read', true),

            -- Pharmacist: pharmacy operations
            (gen_random_uuid(), 'PHARMACIST', 'patients', 'read', true),
            (gen_random_uuid(), 'PHARMACIST', 'pharmacy', 'read', true),
            (gen_random_uuid(), 'PHARMACIST', 'pharmacy', 'write', true),
            (gen_random_uuid(), 'PHARMACIST', 'prescriptions', 'read', true),

            -- Manager: operational oversight
            (gen_random_uuid(), 'MANAGER', 'patients', 'read', true),
            (gen_random_uuid(), 'MANAGER', 'reports', 'read', true),
            (gen_random_uuid(), 'MANAGER', 'billing', 'read', true),
            (gen_random_uuid(), 'MANAGER', 'analytics', 'read', true),

            -- Lab Tech: lab operations
            (gen_random_uuid(), 'LAB_TECH', 'patients', 'read', true),
            (gen_random_uuid(), 'LAB_TECH', 'lab', 'read', true),
            (gen_random_uuid(), 'LAB_TECH', 'lab', 'write', true),
            (gen_random_uuid(), 'LAB_TECH', 'samples', 'read', true),
            (gen_random_uuid(), 'LAB_TECH', 'samples', 'write', true),

            -- Radiologist: imaging operations
            (gen_random_uuid(), 'RADIOLOGIST', 'patients', 'read', true),
            (gen_random_uuid(), 'RADIOLOGIST', 'imaging', 'read', true),
            (gen_random_uuid(), 'RADIOLOGIST', 'imaging', 'write', true),
            (gen_random_uuid(), 'RADIOLOGIST', 'radiology_reports', 'write', true)
        ON CONFLICT (role_code, resource, action) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop all identity tables and schema."""
    op.drop_table("outbox", schema="identity")
    op.drop_table("permissions", schema="identity")
    op.drop_table("otp_codes", schema="identity")
    op.drop_table("refresh_tokens", schema="identity")
    op.drop_table("user_sessions", schema="identity")
    op.drop_table("users", schema="identity")
    op.drop_table("roles", schema="identity")
    op.execute("DROP SCHEMA IF EXISTS identity CASCADE")
