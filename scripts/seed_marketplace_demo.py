"""Seed demo clinics for the "Find a Doctor" marketplace.

"Find a Doctor" (/find-doctor) khali lage? Ye script 8 demo clinics (alag city +
specialty + lat/long) clinics table me daal deta hai — taaki marketplace turant
"alive" dikhe. **Idempotent** hai: clinic_code match hone par skip karta hai
(dobara chalane par duplicate nahi bante).

Chalana (project root se):
    python scripts/seed_marketplace_demo.py

Demo clinics ko admin panel (/admin) se edit/delete kar sakte hain — ye asli
ClinicModel rows hain, koi fake/mock nahi.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows console par emoji (✅) print hone ke liye UTF-8 force karo (cp1252 crash na ho)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Project root ko sys.path me (agar script kahin se bhi chale)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import sqlalchemy as sa  # noqa: E402

import main_v2  # noqa: E402  (env + DB URL + async session setup)

from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.shared.domain.base_entity import uuid7  # noqa: E402
from src.shared.infrastructure.database import (  # noqa: E402
    Base,
    async_session_factory,
)

DEMO_CLINICS = [
    # (clinic_code, clinic_name, doctor_name, degree, specialty, city, state, lat, lon, phone)
    ("DEMO-001", "Gill Heart & Multispeciality Clinic", "G.S. Gill", "MD, DM (Cardiology)",
     "Cardiology", "Jodhpur", "Rajasthan", 26.2389, 73.0243, "9829012345"),
    ("DEMO-002", "Sharma Family Clinic", "Anita Sharma", "MBBS, MD (Medicine)",
     "General Physician", "Jodhpur", "Rajasthan", 26.2700, 73.0200, "9829023456"),
    ("DEMO-003", "Gupta Ortho & Joint Care", "Ramesh Gupta", "MS (Orthopedics)",
     "Orthopedics", "Jaipur", "Rajasthan", 26.9124, 75.7873, "9829034567"),
    ("DEMO-004", "Verma Child Care", "Priya Verma", "MD (Pediatrics)",
     "Pediatrics", "Jaipur", "Rajasthan", 26.9100, 75.7900, "9829045678"),
    ("DEMO-005", "Mehta Skin & Hair Clinic", "Arjun Mehta", "MD (Dermatology)",
     "Dermatology", "Ahmedabad", "Gujarat", 23.0225, 72.5714, "9829056789"),
    ("DEMO-006", "Rao Women's Wellness", "Sunita Rao", "MS (Gynecology)",
     "Gynecology", "Ahmedabad", "Gujarat", 23.0300, 72.5800, "9829067890"),
    ("DEMO-007", "Patel General Clinic", "Karan Patel", "MBBS, MD",
     "General Physician", "Delhi", "Delhi", 28.6139, 77.2090, "9829078901"),
    ("DEMO-008", "Singh Cardiac Centre", "Neha Singh", "MD, DM (Cardiology)",
     "Cardiology", "Delhi", "Delhi", 28.6200, 77.2100, "9829089012"),
]


async def seed() -> dict:
    """Insert demo clinics (idempotent). Returns {created, skipped}."""
    # Startup: tables + missing columns (same as app lifespan)
    Base.metadata.create_all(bind=main_v2.engine)
    main_v2._migrate_sqlite_columns()

    created = 0
    skipped = 0
    async with async_session_factory() as session:
        for code, cname, dname, degree, spec, city, state, lat, lon, phone in DEMO_CLINICS:
            row = await session.execute(
                sa.select(ClinicModel).where(ClinicModel.clinic_code == code)
            )
            if row.scalar_one_or_none() is not None:
                skipped += 1
                continue
            session.add(
                ClinicModel(
                    id=uuid7(),
                    clinic_name=cname,
                    clinic_code=code,
                    doctor_name=dname,
                    doctor_degree=degree,
                    doctor_phone=phone,
                    specialty=spec,
                    city=city,
                    state=state,
                    address=f"{city}, {state}",
                    latitude=lat,
                    longitude=lon,
                    is_license_active=True,
                    is_active=True,
                    created_by="seed_script",
                )
            )
            created += 1
        await session.commit()
    return {"created": created, "skipped": skipped}


def main() -> None:
    result = asyncio.run(seed())
    print(f"\n✅ Marketplace seed done — created {result['created']}, skipped {result['skipped']} (already present).")
    print("   Ab /find-doctor par city + specialty se doctors dikhenge (partner clinics 🟢 LIVE QUEUE).")
    print("   Demo clinics admin panel (/admin) se edit/delete kar sakte hain.")


if __name__ == "__main__":
    main()
