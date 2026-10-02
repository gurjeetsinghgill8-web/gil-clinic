"""OTP (one-time password) request/response schemas.

Pydantic v2 models for OTP generation and verification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestOtpRequest(BaseModel):
    """Request body for requesting an OTP."""

    user_id: str = Field(
        ...,
        description="UUID of the user requesting an OTP.",
    )
    purpose: str = Field(
        default="login",
        description="OTP purpose: 'login', 'pin_reset', or 'mfa'.",
    )


class VerifyOtpRequest(BaseModel):
    """Request body for verifying an OTP."""

    user_id: str = Field(
        ...,
        description="UUID of the user verifying the OTP.",
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit OTP code.",
    )
    purpose: str = Field(
        default="login",
        description="OTP purpose: 'login', 'pin_reset', or 'mfa'.",
    )


class OtpResponse(BaseModel):
    """Response body for OTP request."""

    message: str = Field(default="OTP sent successfully.")
    otp: str | None = Field(
        default=None,
        description="OTP code (only returned in dev mode; production delivers via SMS/email).",
    )


class OtpVerifiedResponse(BaseModel):
    """Response body for OTP verification."""

    verified: bool = Field(default=True)
    message: str = Field(default="OTP verified successfully.")
