"""End-to-end test for Queue Lite workflow.

Tests the complete flow without a real database:
1. Create a patient (in-memory)
2. Register for tests (QueueEntry creation)
3. Technician actions (call → start → complete → report-ready → deliver)
4. Patient status check

Uses mock repositories with in-memory dicts.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest

from src.domain.queue.entities.queue_entry import QueueEntry
from src.domain.queue.value_objects.queue_status import QueueStatus
from src.domain.queue.ports.queue_repository import QueueRepository
from src.domain.patient.entities.patient import Patient
from src.domain.patient.ports.patient_repository import PatientRepository
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.contact_info import ContactInfo
from src.domain.patient.value_objects.patient_status import PatientStatus

from src.application.common.command import Command
from src.application.queue.use_cases.create_queue_use_case import CreateQueueUseCase
from src.application.queue.use_cases.list_queue_use_case import ListQueueUseCase
from src.application.queue.use_cases.technician_action_use_case import (
    TechnicianActionUseCase,
)
from src.application.queue.use_cases.patient_queue_use_case import (
    PatientQueueUseCase,
)


# =============================================================================
# In-Memory Mock Repositories
# =============================================================================


class InMemoryQueueRepository(QueueRepository):
    """In-memory queue repo for testing."""

    def __init__(self):
        self._entries: dict[str, QueueEntry] = {}
        self._token_counters: dict[str, int] = {}

    async def save(self, entry: QueueEntry) -> None:
        entry.touch()
        self._entries[str(entry.id)] = entry

    async def save_many(self, entries: list[QueueEntry]) -> None:
        for e in entries:
            await self.save(e)

    async def get_by_id(self, entry_uuid: str) -> QueueEntry | None:
        return self._entries.get(entry_uuid)

    async def get_active_by_patient(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        return [
            e for e in self._entries.values()
            if e.patient_uuid == patient_uuid and e.is_active
        ]

    async def list_by_department(
        self,
        department: str,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        results = [
            e for e in self._entries.values()
            if e.department == department
        ]
        if status_filter:
            results = [e for e in results if e.status.value == status_filter]
        return sorted(results, key=lambda e: e.token_number)[offset:offset + limit]

    async def list_by_visit(self, visit_id: str) -> list[QueueEntry]:
        return [
            e for e in self._entries.values()
            if e.visit_id == visit_id
        ]

    async def get_next_token_number(
        self, service_code: str, date_prefix: str
    ) -> int:
        key = f"{service_code}:{date_prefix}"
        self._token_counters[key] = self._token_counters.get(key, 0) + 1
        return self._token_counters[key]

    async def get_queue_depth(self, service_code: str) -> int:
        return len([
            e for e in self._entries.values()
            if e.service_code == service_code
            and e.status == QueueStatus.WAITING
        ])

    async def count_by_status(
        self, department: str, status: str
    ) -> int:
        return len([
            e for e in self._entries.values()
            if e.department == department
            and e.status.value == status
        ])

    async def list_patient_queue(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        return sorted(
            [e for e in self._entries.values() if e.patient_uuid == patient_uuid],
            key=lambda e: e.created_at,
            reverse=True,
        )

    async def delete(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)


class InMemoryPatientRepository(PatientRepository):
    """In-memory patient repo for testing."""

    def __init__(self):
        self._patients: dict[str, Patient] = {}
        self._patients_by_id: dict[str, Patient] = {}

    async def save(self, patient: Patient) -> None:
        patient.touch()
        key = str(patient.id)
        self._patients[key] = patient
        self._patients_by_id[patient.patient_id] = patient

    async def get_by_id(self, patient_uuid: str) -> Patient | None:
        return self._patients.get(patient_uuid)

    async def get_by_patient_id(self, patient_id: str) -> Patient | None:
        return self._patients_by_id.get(patient_id)

    async def get_by_phone_hash(self, phone_hash: str) -> Patient | None:
        for p in self._patients.values():
            if p.contact_info.phone_hash == phone_hash:
                return p
        return None

    async def find_by_name(
        self, name: str, limit: int = 10
    ) -> list[Patient]:
        return [
            p for p in self._patients.values()
            if name.lower() in p.demographics.name.lower()
        ][:limit]

    async def list_all(self, offset: int = 0, limit: int = 100) -> list[Patient]:
        return list(self._patients.values())[offset:offset + limit]

    async def get_by_qr_hash(self, qr_hash: str) -> Patient | None:
        for p in self._patients.values():
            if p.qr_identity and p.qr_identity.qr_hash == qr_hash:
                return p
        return None

    async def get_next_sequence_number(self, date_prefix: str) -> int:
        return len(self._patients) + 1

    async def delete(self, patient_id: str) -> None:
        self._patients.pop(patient_id, None)
        self._patients_by_id = {
            k: v for k, v in self._patients_by_id.items()
            if str(v.id) != patient_id
        }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def queue_repo():
    return InMemoryQueueRepository()


@pytest.fixture
def patient_repo():
    return InMemoryPatientRepository()


@pytest.fixture
async def test_patient(patient_repo):
    """Create a test patient."""
    demographics = Demographics.create(
        name="Rahul Sharma",
        age=45,
        gender="male",
    )
    contact = ContactInfo.create(
        phone="9876543210",
        phone_hash=hashlib.sha256(b"9876543210").hexdigest(),
    )
    patient = Patient.register(
        patient_id="CQ-20260714-001",
        demographics=demographics,
        contact=contact,
    )
    await patient_repo.save(patient)
    return patient


# =============================================================================
# E2E Workflow Tests
# =============================================================================


class TestReceptionToPatientWorkflow:
    """Complete workflow: Reception → Queue → Technician → Patient PWA."""

    @pytest.mark.asyncio
    async def test_1_reception_registers_patient(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 1: Reception registers patient for tests."""
        use_case = CreateQueueUseCase(
            queue_repo=queue_repo,
            patient_repo=patient_repo,
        )

        command = Command(data={
            "patient_id": test_patient.patient_id,
            "services": ["ECG", "ECHO"],
            "created_by": "reception",
        })
        result = await use_case.run(command)

        assert result.is_ok
        data = result.data
        assert data["patient_id"] == test_patient.patient_id
        assert data["total_entries"] == 2

        # Verify both queue entries created
        entries = data["entries"]
        codes = [e["service_code"] for e in entries]
        assert "ECG" in codes
        assert "ECHO" in codes

        # Store visit_id for next tests
        self.visit_id = data["visit_id"]
        self.entry_ids = {e["service_code"]: e["id"] for e in entries}

    @pytest.mark.asyncio
    async def test_2_technician_sees_queue(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 2: Technician opens dashboard and sees waiting patients."""
        await self.test_1_reception_registers_patient(
            queue_repo, patient_repo, test_patient
        )

        use_case = ListQueueUseCase(queue_repo=queue_repo)
        command = Command(data={
            "department": "Cardiology",
        })
        result = await use_case.run(command)

        assert result.is_ok
        data = result.data
        assert data["total"] >= 2
        assert data["stats"]["waiting"] >= 2

        # Find our patient's entries
        ecg_entry = next(
            e for e in data["entries"]
            if e["service_code"] == "ECG"
        )
        assert ecg_entry["status"] == "WAITING"
        assert ecg_entry["is_active"]

    @pytest.mark.asyncio
    async def test_3_technician_calls_patient(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 3: Technician calls patient for ECG."""
        await self.test_1_reception_registers_patient(
            queue_repo, patient_repo, test_patient
        )

        # Get the ECG entry
        list_use_case = ListQueueUseCase(queue_repo=queue_repo)
        dashboard = await list_use_case.run(Command(data={"department": "Cardiology"}))
        ecg_entry = next(
            e for e in dashboard.data["entries"]
            if e["service_code"] == "ECG"
        )

        # Call the patient
        action_use_case = TechnicianActionUseCase(queue_repo=queue_repo)
        command = Command(data={
            "entry_id": ecg_entry["id"],
            "action": "call",
            "updated_by": "tech1",
        })
        result = await action_use_case.run(command)

        assert result.is_ok
        assert result.data["action"] == "call"

        # Verify transition
        updated = await queue_repo.get_by_id(ecg_entry["id"])
        assert updated.status == QueueStatus.CALLED
        assert updated.called_at is not None

    @pytest.mark.asyncio
    async def test_4_full_lifecycle(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 4: Complete lifecycle for one test."""
        await self.test_1_reception_registers_patient(
            queue_repo, patient_repo, test_patient
        )

        action = TechnicianActionUseCase(queue_repo=queue_repo)
        ecg_id = self.entry_ids["ECG"]

        # Call → Start → Complete → Report Ready → Deliver
        steps = ["call", "start", "complete", "report-ready", "deliver"]
        expected_statuses = [
            QueueStatus.CALLED,
            QueueStatus.IN_PROGRESS,
            QueueStatus.COMPLETED,
            QueueStatus.REPORT_READY,
            QueueStatus.DELIVERED,
        ]

        for step, expected in zip(steps, expected_statuses):
            cmd = Command(data={
                "entry_id": ecg_id,
                "action": step,
                "updated_by": "tech1",
            })
            result = await action.run(cmd)
            assert result.is_ok, f"{step} failed: {result.error}"

            entry = await queue_repo.get_by_id(ecg_id)
            assert entry.status == expected, (
                f"After {step}, expected {expected.value}, got {entry.status.value}"
            )

        # Terminal check
        entry = await queue_repo.get_by_id(ecg_id)
        assert entry.is_terminal
        assert entry.status == QueueStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_5_patient_views_status(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 5: Patient opens their PWA dashboard."""
        await self.test_1_reception_registers_patient(
            queue_repo, patient_repo, test_patient
        )

        # Call one entry
        action = TechnicianActionUseCase(queue_repo=queue_repo)
        await action.run(Command(data={
            "entry_id": self.entry_ids["ECG"],
            "action": "call",
            "updated_by": "tech1",
        }))

        # Patient views status
        use_case = PatientQueueUseCase(
            queue_repo=queue_repo,
            patient_repo=patient_repo,
        )
        command = Command(data={
            "patient_uuid": str(test_patient.id),
        })
        result = await use_case.run(command)

        assert result.is_ok
        data = result.data
        assert data["patient_id"] == test_patient.patient_id
        assert data["patient_name"] == "Rahul Sharma"
        assert data["active_count"] >= 1  # ECG is called, Echo still waiting

        # Check ECGs status is called
        ecg = next(e for e in data["entries"] if e["service_code"] == "ECG")
        assert ecg["status"] == "CALLED"

        # Check Echo is still waiting
        echo = next(e for e in data["entries"] if e["service_code"] == "ECHO")
        assert echo["status"] == "WAITING"

        # Verify wait time is calculated
        assert ecg["wait_minutes"] >= 0
        assert echo["wait_minutes"] >= 0

    @pytest.mark.asyncio
    async def test_6_invalid_transition_rejected(
        self, queue_repo, patient_repo, test_patient
    ):
        """Step 6: Invalid transitions are properly rejected."""
        await self.test_1_reception_registers_patient(
            queue_repo, patient_repo, test_patient
        )

        action = TechnicianActionUseCase(queue_repo=queue_repo)
        ecg_id = self.entry_ids["ECG"]

        # Cannot complete from WAITING
        cmd = Command(data={
            "entry_id": ecg_id,
            "action": "complete",
            "updated_by": "tech1",
        })
        result = await action.run(cmd)
        assert result.is_fail

        # Call first
        await action.run(Command(data={
            "entry_id": ecg_id,
            "action": "call",
            "updated_by": "tech1",
        }))

        # Cannot deliver from CALLED
        cmd = Command(data={
            "entry_id": ecg_id,
            "action": "deliver",
            "updated_by": "tech1",
        })
        result = await action.run(cmd)
        assert result.is_fail

    @pytest.mark.asyncio
    async def test_7_multiple_patients_independent(
        self, queue_repo, patient_repo
    ):
        """Step 7: Multiple patients with independent queues."""
        # Register two patients
        d1 = Demographics.create(name="Patient One", age=30, gender="male")
        c1 = ContactInfo.create(phone="1111111111", phone_hash=hashlib.sha256(b"1111111111").hexdigest())
        p1 = Patient.register(patient_id="CQ-20260714-002", demographics=d1, contact=c1)

        d2 = Demographics.create(name="Patient Two", age=25, gender="female")
        c2 = ContactInfo.create(phone="2222222222", phone_hash=hashlib.sha256(b"2222222222").hexdigest())
        p2 = Patient.register(patient_id="CQ-20260714-003", demographics=d2, contact=c2)

        await patient_repo.save(p1)
        await patient_repo.save(p2)

        # Register both for same test
        create = CreateQueueUseCase(queue_repo=queue_repo, patient_repo=patient_repo)

        r1 = await create.run(Command(data={
            "patient_id": p1.patient_id,
            "services": ["ECG"],
            "created_by": "reception",
        }))
        assert r1.is_ok

        r2 = await create.run(Command(data={
            "patient_id": p2.patient_id,
            "services": ["ECG"],
            "created_by": "reception",
        }))
        assert r2.is_ok

        # Verify both have different token numbers
        t1 = r1.data["entries"][0]["token_number"]
        t2 = r2.data["entries"][0]["token_number"]
        assert t1 != t2

        # Call p1 — should not affect p2
        action = TechnicianActionUseCase(queue_repo=queue_repo)
        p1_entry_id = r1.data["entries"][0]["id"]
        await action.run(Command(data={
            "entry_id": p1_entry_id,
            "action": "call",
            "updated_by": "tech1",
        }))

        # Verify p1 is called
        p1_entry = await queue_repo.get_by_id(p1_entry_id)
        assert p1_entry.status == QueueStatus.CALLED

        # Verify p2 is still waiting
        p2_entry_id = r2.data["entries"][0]["id"]
        p2_entry = await queue_repo.get_by_id(p2_entry_id)
        assert p2_entry.status == QueueStatus.WAITING
