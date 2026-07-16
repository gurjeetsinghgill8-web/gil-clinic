"""JSON file storage provider for Departments and Services.

Reads/writes `departments.json` and `services.json` in the
cardioqueue_data/ directory with atomic write + .bak recovery.

Seeds default data if files don't exist.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.domain.clinic.entities.department import Department
from src.domain.clinic.entities.service import Service

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("GHOS_DATA_DIR", "cardioqueue_data"))

DEPARTMENTS_FILE = DATA_DIR / "departments.json"
SERVICES_FILE = DATA_DIR / "services.json"

# ---------------------------------------------------------------------------
# Default seed data
# ---------------------------------------------------------------------------

DEFAULT_DEPARTMENTS: list[dict[str, Any]] = [
    {"code": "CARDIO", "name": "Cardiology", "description": "Cardiology Department", "is_active": True, "display_order": 1},
]

DEFAULT_SERVICES: list[dict[str, Any]] = [
    {"code": "ECG", "display_name": "Electrocardiogram", "department_code": "CARDIO", "room_name": "ECG Room 1", "avg_test_time": 10, "is_active": True},
    {"code": "Echo", "display_name": "Echocardiogram", "department_code": "CARDIO", "room_name": "Echo Room 1", "avg_test_time": 20, "is_active": True},
    {"code": "TMT", "display_name": "Treadmill Test", "department_code": "CARDIO", "room_name": "TMT Room 1", "avg_test_time": 30, "is_active": True},
    {"code": "Holter", "display_name": "Holter Monitor", "department_code": "CARDIO", "room_name": "Holter Room", "avg_test_time": 15, "is_active": True},
    {"code": "ABPM", "display_name": "Ambulatory BP Monitor", "department_code": "CARDIO", "room_name": "ABPM Room", "avg_test_time": 15, "is_active": True},
    {"code": "OPD", "display_name": "OPD Consultation", "department_code": "CARDIO", "room_name": "OPD Room", "avg_test_time": 10, "is_active": True},
    {"code": "X-Ray", "display_name": "X-Ray", "department_code": "CARDIO", "room_name": "X-Ray Room 1", "avg_test_time": 10, "is_active": True},
    {"code": "Ultrasound", "display_name": "Ultrasound", "department_code": "CARDIO", "room_name": "Ultrasound Room 1", "avg_test_time": 20, "is_active": True},
]

# ---------------------------------------------------------------------------
# Atomic file I/O helpers
# ---------------------------------------------------------------------------


def _ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, data: list[dict[str, Any]]) -> None:
    """Atomically write JSON data to a file.

    Writes to a temp file in the same directory, then renames it.
    A .bak copy is kept for recovery.
    """
    _ensure_data_dir()
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp.replace(path)
        # Keep a .bak copy for recovery
        shutil.copy2(path, path.with_suffix(".json.bak"))
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _safe_read(path: Path) -> list[dict[str, Any]] | None:
    """Safely read JSON data from a file, falling back to .bak if corrupted."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError, OSError):
        bak = path.with_suffix(".json.bak")
        if bak.exists():
            try:
                with open(bak, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None


# ---------------------------------------------------------------------------
# Seed / Initialize
# ---------------------------------------------------------------------------


def _seed_defaults() -> None:
    """Write default departments and services if files don't exist."""
    if not DEPARTMENTS_FILE.exists():
        _ensure_data_dir()
        now = datetime.now(timezone.utc).isoformat()
        for dept in DEFAULT_DEPARTMENTS:
            dept["created_at"] = now
            dept["updated_at"] = now
        _atomic_write(DEPARTMENTS_FILE, DEFAULT_DEPARTMENTS)

    if not SERVICES_FILE.exists():
        now = datetime.now(timezone.utc).isoformat()
        for svc in DEFAULT_SERVICES:
            svc["created_at"] = now
            svc["updated_at"] = now
        _atomic_write(SERVICES_FILE, DEFAULT_SERVICES)


# ---------------------------------------------------------------------------
# Department CRUD
# ---------------------------------------------------------------------------


def _load_departments() -> list[dict[str, Any]]:
    """Load all departments from JSON file, seeding if needed."""
    _seed_defaults()
    data = _safe_read(DEPARTMENTS_FILE)
    if data is None:
        _seed_defaults()
        data = _safe_read(DEPARTMENTS_FILE)
    return data or []


def _save_departments(departments: list[dict[str, Any]]) -> None:
    """Save departments to JSON file."""
    _atomic_write(DEPARTMENTS_FILE, departments)


def get_all_departments() -> list[Department]:
    """Return all departments as domain entities."""
    return [Department.from_dict(d) for d in _load_departments()]


def get_active_departments() -> list[Department]:
    """Return active departments sorted by display_order."""
    depts = get_all_departments()
    return sorted(
        [d for d in depts if d.is_active],
        key=lambda d: d.display_order,
    )


def get_department_by_code(code: str) -> Department | None:
    """Find a department by its unique code."""
    for d in get_all_departments():
        if d.code.upper() == code.upper():
            return d
    return None


def save_department(department: Department) -> None:
    """Upsert a department. Inserts if new, updates if exists."""
    departments = _load_departments()
    idx = _find_index(departments, "code", department.code)
    dept_dict = department.to_dict()
    if idx is not None:
        departments[idx] = dept_dict
    else:
        departments.append(dept_dict)
    _save_departments(departments)


def delete_department(code: str) -> bool:
    """Delete a department by code. Returns True if deleted."""
    departments = _load_departments()
    idx = _find_index(departments, "code", code)
    if idx is not None:
        departments.pop(idx)
        _save_departments(departments)
        return True
    return False


def department_exists(code: str) -> bool:
    """Check if a department with the given code exists."""
    return get_department_by_code(code) is not None


# ---------------------------------------------------------------------------
# Service CRUD
# ---------------------------------------------------------------------------


def _load_services() -> list[dict[str, Any]]:
    """Load all services from JSON file, seeding if needed."""
    _seed_defaults()
    data = _safe_read(SERVICES_FILE)
    if data is None:
        _seed_defaults()
        data = _safe_read(SERVICES_FILE)
    return data or []


def _save_services(services: list[dict[str, Any]]) -> None:
    """Save services to JSON file."""
    _atomic_write(SERVICES_FILE, services)


def get_all_services() -> list[Service]:
    """Return all services as domain entities."""
    return [Service.from_dict(s) for s in _load_services()]


def get_active_services() -> list[Service]:
    """Return only active services."""
    return [s for s in get_all_services() if s.is_active]


def get_services_by_department(department_code: str) -> list[Service]:
    """Return all services for a given department."""
    return [s for s in get_all_services() if s.department_code.upper() == department_code.upper()]


def get_active_services_by_department(department_code: str) -> list[Service]:
    """Return active services for a given department."""
    return [s for s in get_active_services() if s.department_code.upper() == department_code.upper()]


def get_service_by_code(code: str) -> Service | None:
    """Find a service by its unique code."""
    for s in get_all_services():
        if s.code == code:
            return s
    return None


def save_service(service: Service) -> None:
    """Upsert a service. Inserts if new, updates if exists."""
    services = _load_services()
    idx = _find_index(services, "code", service.code)
    svc_dict = service.to_dict()
    if idx is not None:
        services[idx] = svc_dict
    else:
        services.append(svc_dict)
    _save_services(services)


def delete_service(code: str) -> bool:
    """Delete a service by code. Returns True if deleted."""
    services = _load_services()
    idx = _find_index(services, "code", code)
    if idx is not None:
        services.pop(idx)
        _save_services(services)
        return True
    return False


def service_exists(code: str) -> bool:
    """Check if a service with the given code exists."""
    return get_service_by_code(code) is not None


# ---------------------------------------------------------------------------
# Reset to defaults
# ---------------------------------------------------------------------------


def reset_to_defaults() -> None:
    """Reset departments and services to hardcoded defaults."""
    now = datetime.now(timezone.utc).isoformat()
    for dept in DEFAULT_DEPARTMENTS:
        dept["created_at"] = now
        dept["updated_at"] = now
    _atomic_write(DEPARTMENTS_FILE, DEFAULT_DEPARTMENTS)

    for svc in DEFAULT_SERVICES:
        svc["created_at"] = now
        svc["updated_at"] = now
    _atomic_write(SERVICES_FILE, DEFAULT_SERVICES)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_index(items: list[dict], key: str, value: str) -> int | None:
    """Find the index of an item in a list of dicts by a key value."""
    for i, item in enumerate(items):
        if str(item.get(key, "")).upper() == value.upper():
            return i
    return None


def get_service_map() -> dict[str, Service]:
    """Return a dict mapping service_code → Service for quick lookups.

    Useful for replacing hardcoded SERVICE_NAMES, ROOM_MAPPINGS, AVG_TEST_TIME.
    """
    return {s.code: s for s in get_all_services()}
