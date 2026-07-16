"""Shared infrastructure layer — reusable database, Redis, logging, encryption.

Provides:
- Base: SQLAlchemy declarative base for all models
- get_session: FastAPI async session dependency
- unit_of_work: Transaction context manager
- get_redis: Redis client for pub/sub and caching
- configure_logging: Structured JSON/colored logging
- encrypt/decrypt: AES-256-GCM for PII at rest
"""

from src.shared.infrastructure.database import (
    Base,
    check_database_health,
    get_session,
    unit_of_work,
)
from src.shared.infrastructure.encryption import (
    decrypt,
    encrypt,
    encrypt_searchable,
    hash_for_search,
)
from src.shared.infrastructure.logging import configure_logging, get_logger
from src.shared.infrastructure.redis_client import (
    check_redis_health,
    close_redis,
    get_redis,
    publish_event,
)

__all__ = [
    "Base",
    "get_session",
    "unit_of_work",
    "check_database_health",
    "get_redis",
    "close_redis",
    "publish_event",
    "check_redis_health",
    "configure_logging",
    "get_logger",
    "encrypt",
    "decrypt",
    "hash_for_search",
    "encrypt_searchable",
]
