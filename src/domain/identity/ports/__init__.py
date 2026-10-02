"""Port interfaces (Protocols) for infrastructure adapters.

Ports are defined in the domain layer and implemented in the infrastructure layer.
This enables dependency inversion — domain never depends on infrastructure.
"""

from src.domain.identity.ports.event_publisher import EventPublisher
from src.domain.identity.ports.otp_service import OtpService
from src.domain.identity.ports.pin_hasher import PinHasher
from src.domain.identity.ports.token_service import TokenService
from src.domain.identity.ports.user_repository import UserRepository
from src.domain.identity.ports.session_repository import SessionRepository
from src.domain.identity.ports.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.domain.identity.ports.role_repository import RoleRepository
from src.domain.identity.ports.otp_repository import OtpRepository

__all__ = [
    "PinHasher",
    "TokenService",
    "OtpService",
    "EventPublisher",
    "UserRepository",
    "SessionRepository",
    "RefreshTokenRepository",
    "RoleRepository",
    "OtpRepository",
]
