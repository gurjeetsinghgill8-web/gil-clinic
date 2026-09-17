"""Seed a test patient for the Patient Portal UI check (scratch — not shipped)."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GHOS_DB_URL", "sqlite:///./test_portal_ui.db")

import sqlalchemy as sa  # noqa: E402

import main_v2  # noqa: E402
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402

PID = "GIL-UI-001"
PHONE = "9876543210"

main_v2.Base.metadata.create_all(bind=main_v2.engine)
with main_v2.SessionLocal() as session:
    existing = session.execute(
        sa.select(PatientModel).where(PatientModel.patient_id == PID)
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            PatientModel(
                patient_id=PID,
                name="Raj Kumar",
                age=58,
                gender="M",
                phone=PHONE,
                phone_hash=hashlib.sha256(PHONE.encode()).hexdigest(),
            )
        )
        session.commit()
        print("seeded", PID)
    else:
        print("already present", PID)
