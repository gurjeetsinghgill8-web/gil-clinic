"""Experience Engine — FastAPI dependency injection.

Provides use case factories and session management for the patient experience.
Supports dual backend: SQLAlchemy (default) or JSON file storage (GHOS_DB_BACKEND=json).
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.experience.application.use_cases import (
    PatientLoginUseCase,
    PatientStatusUseCase,
    PatientTimelineUseCase,
    TokenSlipUseCase,
    PatientInquiryUseCase,
    PatientAlertUseCase,
    FeedbackUseCase,
    get_patient_from_session,
)
from src.infrastructure.patient.services.qr_code_generator import (
    PatientQRCodeGenerator,
)
from src.shared.infrastructure.database import get_session

# ------------------------------------------------------------------
# Backend selection
# ------------------------------------------------------------------

_DB_BACKEND = os.getenv("GHOS_DB_BACKEND", "sqlalchemy").lower()


def _use_json_backend() -> bool:
    """Check if JSON file backend is configured.

    Returns:
        True if GHOS_DB_BACKEND=json or any variant.
    """
    return _DB_BACKEND in ("json", "file", "local", "local-json")


# ------------------------------------------------------------------
# Lazy-loaded patient repo factory
# ------------------------------------------------------------------


async def _get_patient_repo(session=None):
    """Get the appropriate patient repository based on backend config.

    Args:
        session: Optional DB session (ignored for JSON backend).

    Returns:
        PatientRepository implementation (SQLAlchemy or JSON).
    """
    if _use_json_backend():
        from src.infrastructure.persistence.shared.json_repositories import (
            JsonPatientRepository,
        )
        return JsonPatientRepository()
    from src.infrastructure.persistence.patient.repositories.patient_repository import (
        SqlAlchemyPatientRepository,
    )
    return SqlAlchemyPatientRepository(session)


def _get_queue_repo_sync(request: Request = None, session=None):
    """Get the appropriate queue repository (sync).

    Args:
        request: FastAPI request (for sync SQLAlchemy session).
        session: Optional DB session.

    Returns:
        QueueRepository implementation.
    """
    if _use_json_backend():
        from src.infrastructure.persistence.shared.json_repositories import (
            JsonQueueRepository,
        )
        return JsonQueueRepository()
    from src.infrastructure.persistence.queue.repositories.queue_repository import (
        SqlAlchemyQueueRepository,
    )
    if session:
        return SqlAlchemyQueueRepository(session)
    return SqlAlchemyQueueRepository(request.app.state.db_session)


# ------------------------------------------------------------------
# In-memory stores (replace with Redis in production)
# ------------------------------------------------------------------

_qr_generator: PatientQRCodeGenerator | None = None


def get_qr_generator() -> PatientQRCodeGenerator:
    global _qr_generator
    if _qr_generator is None:
        _qr_generator = PatientQRCodeGenerator()
    return _qr_generator


# ------------------------------------------------------------------
# Use Case Factories
# ------------------------------------------------------------------


async def get_login_use_case(
    session: AsyncSession = Depends(get_session),
) -> PatientLoginUseCase:
    repo = await _get_patient_repo(session)
    return PatientLoginUseCase(
        patient_repo=repo,
        qr_code_generator=get_qr_generator(),
    )


async def get_status_use_case(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PatientStatusUseCase:
    patient_repo = await _get_patient_repo(session)
    queue_repo = _get_queue_repo_sync(request=request)
    return PatientStatusUseCase(patient_repo=patient_repo, queue_repo=queue_repo)


async def get_token_slip_use_case(
    session: AsyncSession = Depends(get_session),
) -> TokenSlipUseCase:
    repo = await _get_patient_repo(session)
    return TokenSlipUseCase(patient_repo=repo)


async def get_inquiry_use_case(
    session: AsyncSession = Depends(get_session),
) -> PatientInquiryUseCase:
    repo = await _get_patient_repo(session)
    return PatientInquiryUseCase(patient_repo=repo)


# ------------------------------------------------------------------
# Feedback — uses JSON file backend, no DB needed
# ------------------------------------------------------------------


def get_feedback_use_case() -> FeedbackUseCase:
    """Get FeedbackUseCase (stateless, file-backed)."""
    return FeedbackUseCase()


# ------------------------------------------------------------------
# Patient Alert — uses sync session (Queue Engine)
# ------------------------------------------------------------------


async def get_patient_alert_use_case(
    request: Request,
) -> PatientAlertUseCase:
    """Get PatientAlertUseCase using the configured backend."""
    queue_repo = _get_queue_repo_sync(request=request)
    return PatientAlertUseCase(queue_repo=queue_repo)


# ------------------------------------------------------------------
# Patient Timeline — uses sync session (Queue Engine)
# ------------------------------------------------------------------


async def get_timeline_use_case(
    request: Request,
) -> PatientTimelineUseCase:
    """Get PatientTimelineUseCase using the configured backend."""
    queue_repo = _get_queue_repo_sync(request=request)
    return PatientTimelineUseCase(queue_repo=queue_repo)


# ------------------------------------------------------------------
# Session Dependency
# ------------------------------------------------------------------


async def require_patient_session(
    authorization: str | None = Header(None),
) -> dict:
    """Extract patient context from session token.

    This is the patient-side equivalent of get_current_user().
    Uses a simple bearer token from the login response.

    Args:
        authorization: "Bearer <session_token>" header.

    Returns:
        Patient session dict with patient_uuid, patient_id, phone_hash.

    Raises:
        HTTPException: If token is missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is required. POST /experience/login first.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header. Use: Bearer <session_token>",
        )

    session = get_patient_from_session(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again.",
        )

    return session
