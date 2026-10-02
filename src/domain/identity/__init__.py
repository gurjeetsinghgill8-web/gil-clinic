"""Identity Engine - Domain Layer (DDD, pure Python, no infrastructure).

This package contains the entire domain logic for the Identity Engine:
- Entities: User, Session, RefreshToken, Role
- Value Objects: Permission, DeviceInfo, LockoutResult, OtpCode
- Events: 19 IdentityEvent types (IDENTITY.* CloudEvents)
- Exceptions: 11 DomainError classes (IDENTITY_* error codes)
- Ports: 9 Protocol interfaces for infrastructure adapters
- Policies: LockoutPolicy, SessionPolicy
- Services: AuthenticationService (pure domain orchestration)

Domain rules:
- Identity publishes events only — never makes direct calls to other engines
- Domain depends on nothing outside src/domain/
- Ports are Protocols — infrastructure provides implementations
"""

from src.domain.identity.entities import (
    User,
    Session,
    RefreshToken,
    Role,
)
from src.domain.identity.value_objects import (
    Permission,
    DeviceInfo,
    LockoutResult,
    OtpCode,
)
from src.domain.identity.events import (
    IdentityEvent,
    user_created,
    user_updated,
    user_disabled,
    user_reactivated,
    user_login,
    user_logout,
    otp_sent,
    otp_verified,
    token_refreshed,
    role_assigned,
    login_failed,
    account_locked,
    account_unlocked,
    pin_changed,
    session_expired,
    session_revoked,
    security_alert,
    device_trusted,
    device_untrusted,
)
from src.domain.identity.exceptions import (
    DomainError,
    InvalidPinFormatError,
    AccountLockedError,
    InvalidCredentialsError,
    OtpExpiredError,
    MaxOtpAttemptsError,
    UnauthorizedError,
    SessionExpiredError,
    UserNotFoundError,
    DuplicateUsernameError,
    RoleNotFoundError,
    CannotDeleteLastAdminError,
)
from src.domain.identity.ports import (
    PinHasher,
    TokenService,
    OtpService,
    EventPublisher,
    UserRepository,
    SessionRepository,
    RefreshTokenRepository,
    RoleRepository,
    OtpRepository,
)
from src.domain.identity.services import AuthenticationDomainService as AuthenticationService
from src.domain.identity.policies.lockout_policy import LockoutPolicy
from src.domain.identity.policies.session_policy import SessionPolicy

__all__ = [
    # Entities
    "User",
    "Session",
    "RefreshToken",
    "Role",
    # Value Objects
    "Permission",
    "DeviceInfo",
    "LockoutResult",
    "OtpCode",
    # Events
    "IdentityEvent",
    "user_created",
    "user_updated",
    "user_disabled",
    "user_reactivated",
    "user_login",
    "user_logout",
    "otp_sent",
    "otp_verified",
    "token_refreshed",
    "role_assigned",
    "login_failed",
    "account_locked",
    "account_unlocked",
    "pin_changed",
    "session_expired",
    "session_revoked",
    "security_alert",
    "device_trusted",
    "device_untrusted",
    # Exceptions
    "DomainError",
    "InvalidPinFormatError",
    "AccountLockedError",
    "InvalidCredentialsError",
    "OtpExpiredError",
    "MaxOtpAttemptsError",
    "UnauthorizedError",
    "SessionExpiredError",
    "UserNotFoundError",
    "DuplicateUsernameError",
    "RoleNotFoundError",
    "CannotDeleteLastAdminError",
    # Ports
    "PinHasher",
    "TokenService",
    "OtpService",
    "EventPublisher",
    "UserRepository",
    "SessionRepository",
    "RefreshTokenRepository",
    "RoleRepository",
    "OtpRepository",
    # Services
    "AuthenticationService",
    # Policies
    "LockoutPolicy",
    "SessionPolicy",
]
