"""Queue Lite — FastAPI dependency injection.

Provides factory functions for all Queue Lite use cases.
Supports dual backend: SQLAlchemy (default) or JSON file storage (GHOS_DB_BACKEND=json).
"""

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.queue.use_cases.create_queue_use_case import CreateQueueUseCase
from src.application.queue.use_cases.list_queue_use_case import ListQueueUseCase
from src.application.queue.use_cases.technician_action_use_case import (
    TechnicianActionUseCase,
)
from src.application.queue.use_cases.patient_queue_use_case import (
    PatientQueueUseCase,
)
from src.application.queue.use_cases.doctor_queue_use_case import (
    DoctorQueueUseCase,
)
from src.application.queue.use_cases.alert_use_case import AlertUseCase
from src.application.queue.use_cases.manager_dashboard_use_case import (
    ManagerDashboardUseCase,
)
from src.application.queue.use_cases.tv_alert_use_case import TvAlertUseCase

# ------------------------------------------------------------------
# Backend selection
# ------------------------------------------------------------------

_DB_BACKEND = os.getenv("GHOS_DB_BACKEND", "sqlalchemy").lower()


def _use_json_backend() -> bool:
    """Check if JSON file backend is configured.

    Returns:
        True if GHOS_DB_BACKEND=json or variant.
    """
    return _DB_BACKEND in ("json", "file", "local", "local-json")


# ------------------------------------------------------------------
# Repository factories
# ------------------------------------------------------------------


def _get_queue_repo(session=None):
    """Get the appropriate queue repository based on backend config.

    Args:
        session: Optional DB session (ignored for JSON backend).

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
    return SqlAlchemyQueueRepository(session)


def _get_patient_repo(session=None):
    """Get the appropriate patient repository.

    Args:
        session: Optional DB session (ignored for JSON backend).

    Returns:
        PatientRepository implementation (QueuePatientLookup for SQLite).
    """
    if _use_json_backend():
        from src.infrastructure.persistence.shared.json_repositories import (
            JsonPatientRepository,
        )
        return JsonPatientRepository()
    from src.infrastructure.persistence.queue.repositories.patient_lookup import (
        QueuePatientLookup,
    )
    return QueuePatientLookup(session)


def _get_audit_repo(session=None):
    """Get the appropriate audit repository.

    Args:
        session: Optional DB session (ignored for JSON backend).

    Returns:
        Audit repository implementation.
    """
    if _use_json_backend():
        from src.infrastructure.persistence.shared.json_repositories import (
            JsonAuditRepository,
        )
        return JsonAuditRepository()
    from src.infrastructure.persistence.queue.repositories.audit_repository import (
        SqlAlchemyAuditRepository,
    )
    return SqlAlchemyAuditRepository(session)


# ------------------------------------------------------------------
# FastAPI dependencies
# ------------------------------------------------------------------


async def get_db_session() -> AsyncSession:
    """Get an async DB session from the shared async session factory.

    Session is committed on success, rolled back on error.
    """
    from src.shared.infrastructure.database import async_session_factory

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_queue_repo(
    session: AsyncSession = Depends(get_db_session),
):
    """Get queue repository — routes use this.

    Args:
        session: DB session from FastAPI dependency.

    Returns:
        QueueRepository implementation.
    """
    return _get_queue_repo(session)


def get_audit_repo(
    session: AsyncSession = Depends(get_db_session),
):
    """Get audit repository.

    Args:
        session: DB session from FastAPI dependency.

    Returns:
        Audit repository implementation.
    """
    return _get_audit_repo(session)


def get_patient_repo(
    session: AsyncSession = Depends(get_db_session),
):
    """Get patient repository.

    Args:
        session: DB session from FastAPI dependency.

    Returns:
        PatientRepository implementation.
    """
    return _get_patient_repo(session)


# ------------------------------------------------------------------
# Use case factories
# ------------------------------------------------------------------


def get_create_queue_use_case(
    repo=Depends(get_queue_repo),
    audit_repo=Depends(get_audit_repo),
    patient_repo=Depends(get_patient_repo),
) -> CreateQueueUseCase:
    return CreateQueueUseCase(
        queue_repo=repo,
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )


def get_list_queue_use_case(
    repo=Depends(get_queue_repo),
) -> ListQueueUseCase:
    return ListQueueUseCase(queue_repo=repo)


def get_technician_action_use_case(
    repo=Depends(get_queue_repo),
    audit_repo=Depends(get_audit_repo),
) -> TechnicianActionUseCase:
    return TechnicianActionUseCase(queue_repo=repo, audit_repo=audit_repo)


def get_patient_queue_use_case(
    repo=Depends(get_queue_repo),
    patient_repo=Depends(get_patient_repo),
) -> PatientQueueUseCase:
    return PatientQueueUseCase(queue_repo=repo, patient_repo=patient_repo)


def get_doctor_queue_use_case(
    repo=Depends(get_queue_repo),
    patient_repo=Depends(get_patient_repo),
) -> DoctorQueueUseCase:
    return DoctorQueueUseCase(queue_repo=repo, patient_repo=patient_repo)


def get_alert_use_case(
    repo=Depends(get_queue_repo),
    audit_repo=Depends(get_audit_repo),
) -> AlertUseCase:
    return AlertUseCase(queue_repo=repo, audit_repo=audit_repo)


def get_manager_dashboard_use_case(
    repo=Depends(get_queue_repo),
    audit_repo=Depends(get_audit_repo),
) -> ManagerDashboardUseCase:
    return ManagerDashboardUseCase(queue_repo=repo, audit_repo=audit_repo)


# ------------------------------------------------------------------
# TV Alert — no DB needed, in-memory store
# ------------------------------------------------------------------


def get_tv_alert_use_case() -> TvAlertUseCase:
    """Get TvAlertUseCase (in-memory, no DB dependency)."""
    return TvAlertUseCase()
