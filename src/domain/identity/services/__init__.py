"""Domain services: AuthenticationDomainService (pure domain rules only).

Per Clean Architecture, the domain layer contains ONLY business rules.
All orchestration has been moved to src/application/identity/use_cases/.
"""

from src.domain.identity.services.authentication_service import (
    AuthenticationDomainService,
)

__all__ = [
    "AuthenticationDomainService",
]
