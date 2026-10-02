"""License Scheduler — daily background job to enforce license expiry.

Runs every day at midnight. Checks all clinics with active licenses.
If license_expiry_date < today, marks is_license_active = False.

Also sends warning notifications for licenses expiring within 3 days.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import sqlalchemy as sa
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def _check_and_expire_licenses():
    """Check all active licenses and expire those past their date."""
    today = date.today()
    today_str = today.isoformat()

    try:
        async with async_session_factory() as session:
            # Find all active licenses where expiry has passed
            row = await session.execute(
                sa.select(ClinicModel).where(
                    ClinicModel.is_license_active == True,
                    ClinicModel.license_expiry_date < today_str,
                )
            )
            expired_clinics = row.scalars().all()

            for clinic in expired_clinics:
                clinic.is_license_active = False
                logger.info(
                    "🔴 License EXPIRED: %s | %s | Expiry: %s",
                    clinic.clinic_code,
                    clinic.doctor_name,
                    clinic.license_expiry_date,
                )

            if expired_clinics:
                await session.commit()
                print(f"[SCHEDULER] Expired {len(expired_clinics)} license(s)")

            # Find licenses expiring within 3 days (warning)
            warning_date = today + timedelta(days=3)
            warning_str = warning_date.isoformat()

            row = await session.execute(
                sa.select(ClinicModel).where(
                    ClinicModel.is_license_active == True,
                    ClinicModel.license_expiry_date >= today_str,
                    ClinicModel.license_expiry_date <= warning_str,
                )
            )
            warning_clinics = row.scalars().all()

            for clinic in warning_clinics:
                days_left = (
                    date.fromisoformat(clinic.license_expiry_date) - today
                ).days
                logger.info(
                    "🟡 License EXPIRING SOON: %s | %s | %d days left",
                    clinic.clinic_code,
                    clinic.doctor_name,
                    days_left,
                )

            if warning_clinics:
                print(
                    f"[SCHEDULER] {len(warning_clinics)} license(s) expiring within 3 days"
                )

    except Exception as e:
        logger.error("License scheduler error: %s", e)


def start_license_scheduler():
    """Start the APScheduler daily job for license expiry.

    Called once at application startup.
    """
    scheduler.add_job(
        _check_and_expire_licenses,
        trigger="cron",
        hour=0,
        minute=5,
        id="license_expiry_check",
        name="Daily License Expiry Check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("📅 License scheduler started (daily at 00:05)")
    print("[SCHEDULER] License expiry check scheduled daily at 00:05")


def stop_license_scheduler():
    """Stop the scheduler gracefully on shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("License scheduler stopped")
