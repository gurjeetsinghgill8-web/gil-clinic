"""Identity Engine configuration using pydantic-settings.

Centralized settings for JWT, bcrypt, database, Redis, and OTP.
All values are overridable via environment variables with the GHOS_ prefix.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IdentitySettings(BaseSettings):
    """Configuration for the Identity Engine.

    Settings are loaded from environment variables with the GHOS_ prefix.
    A .env file in the project root is also loaded automatically.

    Example:
        settings = IdentitySettings()
        jwt_secret = settings.JWT_PRIVATE_KEY
    """

    model_config = SettingsConfigDict(
        env_prefix="GHOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://ghos:ghos@localhost:5432/ghos_identity",
        description="PostgreSQL async connection string.",
    )
    DATABASE_ECHO: bool = Field(
        default=False,
        description="Enable SQLAlchemy echo for query logging.",
    )
    DATABASE_POOL_SIZE: int = Field(
        default=10,
        description="Connection pool size.",
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=20,
        description="Max overflow connections.",
    )

    # ------------------------------------------------------------------
    # JWT (RS256 asymmetric keys)
    # ------------------------------------------------------------------
    JWT_PRIVATE_KEY: str = Field(
        default="",
        description="RS256 private key (PEM). Falls back to HS256 with secret if empty.",
    )
    JWT_PUBLIC_KEY: str = Field(
        default="",
        description="RS256 public key (PEM). Falls back to HS256 with secret if empty.",
    )
    JWT_SECRET: str = Field(
        default="ghos-identity-jwt-secret-change-in-production",
        description="HS256 fallback secret when no RSA keys are configured.",
    )
    JWT_ALGORITHM: str = Field(
        default="RS256",
        description="JWT signing algorithm (RS256 or HS256).",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,  # 24 hours
        description="Access token TTL in minutes.",
    )

    # ------------------------------------------------------------------
    # Refresh tokens
    # ------------------------------------------------------------------
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        description="Refresh token TTL in days.",
    )
    REFRESH_TOKEN_BYTES: int = Field(
        default=64,
        description="Random bytes for refresh token generation.",
    )

    # ------------------------------------------------------------------
    # bcrypt / PIN hashing
    # ------------------------------------------------------------------
    BCRYPT_ROUNDS: int = Field(
        default=12,
        description="bcrypt cost factor (OWASP recommended: >= 12).",
    )

    # ------------------------------------------------------------------
    # OTP
    # ------------------------------------------------------------------
    OTP_LENGTH: int = Field(
        default=6,
        description="Number of digits in OTP.",
    )
    OTP_EXPIRY_MINUTES: int = Field(
        default=5,
        description="OTP time-to-live in minutes.",
    )

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    SESSION_DURATION_HOURS: int = Field(
        default=24,
        description="Default session TTL in hours.",
    )
    MAX_CONCURRENT_SESSIONS: int = Field(
        default=10,
        description="Max concurrent sessions per user.",
    )

    # ------------------------------------------------------------------
    # Lockout policy
    # ------------------------------------------------------------------
    MAX_LOGIN_ATTEMPTS: int = Field(
        default=5,
        description="Failed attempts before account lockout.",
    )
    LOCKOUT_DURATION_MINUTES: int = Field(
        default=30,
        description="Account lockout duration in minutes.",
    )

    # ------------------------------------------------------------------
    # Redis (for outbox relay)
    # ------------------------------------------------------------------
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for the outbox relay.",
    )

    # ------------------------------------------------------------------
    # Event outbox
    # ------------------------------------------------------------------
    OUTBOX_POLL_INTERVAL_SECONDS: int = Field(
        default=5,
        description="Outbox relay poll interval in seconds.",
    )
    OUTBOX_MAX_RETRY: int = Field(
        default=3,
        description="Max retries for failed outbox events.",
    )


# Singleton — import this, not IdentitySettings directly
settings = IdentitySettings()
