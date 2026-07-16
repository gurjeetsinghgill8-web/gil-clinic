"""Shared domain kernel — reusable building blocks for all 13 engines.

Every engine reuses these primitives instead of reimplementing them.
This prevents duplication and ensures consistency across GHOS.
"""

from src.shared.domain.aggregate_root import AggregateRoot
from src.shared.domain.base_entity import BaseEntity, uuid7
from src.shared.domain.base_value_object import BaseValueObject
from src.shared.domain.constants import (
    ACCESS_TOKEN_EXPIRY_HOURS,
    ACCOUNT_LOCKOUT_MINUTES,
    BCRYPT_COST,
    DAY,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_PAGE_SIZE,
    DEFAULT_STAFF_PIN,
    HOUR,
    MAX_PAGE_SIZE,
    MAX_SESSIONS_PER_USER,
    MINUTE,
    OTP_EXPIRY_SECONDS,
    OTP_LENGTH,
    OTP_MAX_ATTEMPTS,
    OTP_REQUEST_LIMIT,
    OTP_RESEND_COOLDOWN,
    PIN_MAX_ATTEMPTS,
    PIN_MAX_LENGTH,
    PIN_MIN_LENGTH,
    REFRESH_TOKEN_EXPIRY_DAYS,
    ROLE_HIERARCHY,
    SECOND,
    SESSION_INACTIVITY_TIMEOUT_MINUTES,
    WEEK,
)
from src.shared.domain.result import Error, Ok, Result

__all__ = [
    # Base classes
    "BaseEntity",
    "BaseValueObject",
    "AggregateRoot",
    # Utilities
    "uuid7",
    # Result type
    "Result",
    "Ok",
    "Error",
    # Constants
    "SECOND",
    "MINUTE",
    "HOUR",
    "DAY",
    "WEEK",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PIN_MIN_LENGTH",
    "PIN_MAX_LENGTH",
    "OTP_LENGTH",
    "OTP_EXPIRY_SECONDS",
    "OTP_MAX_ATTEMPTS",
    "PIN_MAX_ATTEMPTS",
    "ACCOUNT_LOCKOUT_MINUTES",
    "SESSION_INACTIVITY_TIMEOUT_MINUTES",
    "MAX_SESSIONS_PER_USER",
    "ACCESS_TOKEN_EXPIRY_HOURS",
    "REFRESH_TOKEN_EXPIRY_DAYS",
    "BCRYPT_COST",
    "OTP_REQUEST_LIMIT",
    "OTP_RESEND_COOLDOWN",
    "ROLE_HIERARCHY",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_STAFF_PIN",
]
