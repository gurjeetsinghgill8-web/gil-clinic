"""Unit of Work implementations for the Identity Engine.

Provides:
- SqlAlchemyIdentityUnitOfWork: SQLAlchemy-backed UoW with all 5 repositories
"""

from src.infrastructure.persistence.identity.unit_of_work.sqlalchemy_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)

__all__ = [
    "SqlAlchemyIdentityUnitOfWork",
]
