"""Clinic Repository — CRUD operations for ClinicModel.

Provides async database operations for clinic management:
- Create new clinic
- Get by id, code, username
- List all clinics with filtering
- Update clinic
- License renewal
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.clinic.models.clinic_model import ClinicModel

logger = logging.getLogger(__name__)


class ClinicRepository:
    """Async repository for ClinicModel operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, clinic: ClinicModel) -> ClinicModel:
        """Create a new clinic record."""
        self._session.add(clinic)
        await self._session.flush()
        logger.info("Clinic created: %s (%s)", clinic.clinic_code, clinic.doctor_name)
        return clinic

    async def get_by_id(self, clinic_id: UUID) -> Optional[ClinicModel]:
        """Get clinic by UUID."""
        row = await self._session.execute(
            sa.select(ClinicModel).where(ClinicModel.id == clinic_id)
        )
        return row.scalar_one_or_none()

    async def get_by_code(self, clinic_code: str) -> Optional[ClinicModel]:
        """Get clinic by clinic_code (e.g., 'CLINIC-001')."""
        row = await self._session.execute(
            sa.select(ClinicModel).where(ClinicModel.clinic_code == clinic_code)
        )
        return row.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[ClinicModel]:
        """Get clinic by login username."""
        row = await self._session.execute(
            sa.select(ClinicModel).where(ClinicModel.clinic_username == username)
        )
        return row.scalar_one_or_none()

    async def list_all(
        self,
        is_active: bool | None = None,
        license_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ClinicModel]:
        """List clinics with optional filters."""
        stmt = sa.select(ClinicModel)

        if is_active is not None:
            stmt = stmt.where(ClinicModel.is_active == is_active)
        if license_active is not None:
            stmt = stmt.where(ClinicModel.is_license_active == license_active)

        stmt = stmt.order_by(ClinicModel.created_at.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(stmt)
        return list(rows.scalars().all())

    async def count_active_licenses(self) -> int:
        """Count clinics with active licenses."""
        row = await self._session.execute(
            sa.select(sa.func.count()).select_from(ClinicModel).where(
                ClinicModel.is_license_active == True
            )
        )
        return row.scalar() or 0

    async def count_expiring_soon(self, days: int = 30) -> int:
        """Count licenses expiring within N days."""
        from datetime import date, timedelta

        today = date.today()
        cutoff = today + timedelta(days=days)

        row = await self._session.execute(
            sa.select(sa.func.count()).select_from(ClinicModel).where(
                ClinicModel.is_license_active == True,
                ClinicModel.license_expiry_date <= cutoff.isoformat(),
                ClinicModel.license_expiry_date >= today.isoformat(),
            )
        )
        return row.scalar() or 0

    async def count_expired(self) -> int:
        """Count expired licenses."""
        row = await self._session.execute(
            sa.select(sa.func.count()).select_from(ClinicModel).where(
                ClinicModel.is_license_active == False
            )
        )
        return row.scalar() or 0

    async def get_next_clinic_code(self) -> str:
        """Generate the next sequential clinic code (CLINIC-XXX)."""
        row = await self._session.execute(
            sa.select(sa.func.count()).select_from(ClinicModel)
        )
        count = row.scalar() or 0
        return f"CLINIC-{count + 1:03d}"

    async def update(self, clinic: ClinicModel) -> ClinicModel:
        """Update an existing clinic."""
        clinic.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return clinic

    async def renew_license(
        self, clinic_code: str, duration_months: int, start_date: str | None = None
    ) -> Optional[ClinicModel]:
        """Renew a clinic's license for given duration."""
        from datetime import date, timedelta

        clinic = await self.get_by_code(clinic_code)
        if not clinic:
            return None

        today = date.today()
        start = date.fromisoformat(start_date) if start_date else today
        expiry = start + timedelta(days=duration_months * 30)

        clinic.license_start_date = start.isoformat()
        clinic.license_expiry_date = expiry.isoformat()
        clinic.license_duration_months = duration_months
        clinic.is_license_active = True
        clinic.updated_at = datetime.now(timezone.utc)

        await self._session.flush()
        logger.info(
            "License renewed for %s until %s", clinic_code, expiry.isoformat()
        )
        return clinic

    async def deactivate(self, clinic_code: str) -> bool:
        """Deactivate a clinic (soft)."""
        clinic = await self.get_by_code(clinic_code)
        if not clinic:
            return False
        clinic.is_active = False
        clinic.is_license_active = False
        clinic.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True
