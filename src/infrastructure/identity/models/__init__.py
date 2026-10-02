"""SQLAlchemy ORM models for identity tables.

All 7 tables in the identity schema:
- identity.users          — Staff users (aggregate root)
- identity.roles          — Role definitions (value object)
- identity.permissions    — Permission assignments (value object)
- identity.user_sessions  — Active sessions (separate aggregate)
- identity.refresh_tokens — Refresh token store (separate aggregate)
- identity.otp_codes      — Ephemeral OTP codes
- identity.outbox         — Outbox for domain events
"""

from src.infrastructure.identity.models.user_model import UserModel
from src.infrastructure.identity.models.session_model import SessionModel
from src.infrastructure.identity.models.refresh_token_model import (
    RefreshTokenModel,
)
from src.infrastructure.identity.models.role_model import RoleModel
from src.infrastructure.identity.models.permission_model import PermissionModel
from src.infrastructure.identity.models.otp_code_model import OtpCodeModel
from src.infrastructure.identity.models.outbox_model import OutboxModel

__all__ = [
    "UserModel",
    "SessionModel",
    "RefreshTokenModel",
    "RoleModel",
    "PermissionModel",
    "OtpCodeModel",
    "OutboxModel",
]
