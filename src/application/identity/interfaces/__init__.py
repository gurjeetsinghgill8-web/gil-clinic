"""Application interfaces for the Identity Engine.

Contains:
- UnitOfWork: Atomic transaction boundary for use cases
"""

from src.application.identity.interfaces.unit_of_work import (
    IdentityUnitOfWork,
)

__all__ = [
    "IdentityUnitOfWork",
]
