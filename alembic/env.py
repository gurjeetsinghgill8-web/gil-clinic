"""Alembic migration environment configuration.

Handles schema "identity" for all identity engine tables.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add src to Python path so models can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Alembic Config object
config = context.config

# Set database URL from environment variable if not already set
db_url = os.getenv("GHOS_DB_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url.replace("+asyncpg", ""))

# Configure logging
if config.config_file_name:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them
from src.infrastructure.identity.models import (  # noqa: E402, F401
    OtpCodeModel,
    OutboxModel,
    PermissionModel,
    RefreshTokenModel,
    RoleModel,
    SessionModel,
    UserModel,
)
from src.infrastructure.patient.models import PatientModel  # noqa: E402, F401
from src.infrastructure.queue.models import (  # noqa: E402, F401
    AuditLogModel,
    QueueEntryModel,
)
from src.shared.infrastructure.database import Base  # noqa: E402

target_metadata = Base.metadata

ALLOWED_SCHEMAS = {"identity", "patient", "queue"}


def include_object(obj, name, type_, reflected, compare_to):
    """Only include identity, patient and queue schema objects in migrations."""
    if hasattr(obj, "schema"):
        return obj.schema in ALLOWED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the SQL to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        version_table="alembic_version_identity",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table="alembic_version_identity",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
