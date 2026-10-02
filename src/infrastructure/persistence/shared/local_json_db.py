"""Local JSON File Storage — Drop-in fallback for SQLAlchemy/PostgreSQL.

When the primary database (PostgreSQL/SQLite) is unavailable or when
GHOS_DB_BACKEND=json is set, all data is stored as human-readable JSON
files in date-stamped folders. No database setup needed.

Folder structure:
  cardioqueue_data/
    ├── 2026-07-14/
    │   ├── patients.json           # All patients registered today
    │   ├── queue_entries.json      # All queue entries created today
    │   └── meta.json               # Counters, sequence numbers
    ├── 2026-07-15/
    │   ├── ...
    └── meta.json                   # All-time references (all_patients_index)

Design principles:
- One JSON file per entity type per day (not per entity)
- Files are atomically written via write + rename
- Human-readable with indent=2, ensure_ascii=False
- Date-stamped folders for easy retention/cleanup
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = os.getenv("GHOS_JSON_DATA_DIR", "cardioqueue_data")


def _today_str() -> str:
    """Get today's ISO date string."""
    return date.today().isoformat()


def _today_dir() -> str:
    """Get today's date-stamped folder path, create if missing.

    Returns:
        Absolute path to today's data directory.
    """
    d = _today_str()
    path = os.path.join(DATA_DIR, d)
    os.makedirs(path, exist_ok=True)
    return path


def _now_str() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Atomic file I/O
# ---------------------------------------------------------------------------


def _atomic_write(path: str, data: Any) -> None:
    """Atomically write JSON data to a file.

    Uses write-to-temp + rename to prevent partial writes.
    Also writes a `.bak` copy for recovery.

    Args:
        path: Target file path.
        data: JSON-serializable data to write.
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Write to temp file first
    fd, tmp_path = tempfile.mkstemp(
        suffix=".json",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=_json_default)
        # Rename atomically (best-effort on Windows)
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _safe_read(path: str) -> Any | None:
    """Read JSON data from a file, returning None if missing/corrupt.

    Args:
        path: File path to read.

    Returns:
        Parsed JSON data, or None if file doesn't exist or is corrupt.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Try backup
        bak_path = path + ".bak"
        if os.path.exists(bak_path):
            try:
                with open(bak_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return None


def _json_default(obj: Any) -> str:
    """JSON serializer for non-serializable types (datetime, UUID).

    Args:
        obj: Object to serialize.

    Returns:
        ISO-formatted string or string representation.

    Raises:
        TypeError: If the object type is not supported.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.hex()
    try:
        return str(obj)
    except Exception:
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ---------------------------------------------------------------------------
# Patient storage helpers
# ---------------------------------------------------------------------------


def _patients_file(date_str: str | None = None) -> str:
    """Get path to the patients JSON file for a given date.

    Args:
        date_str: Date string in ISO format. Defaults to today.

    Returns:
        Full path to patients.json.
    """
    d = date_str or _today_str()
    return os.path.join(DATA_DIR, d, "patients.json")


def load_patients(date_str: str | None = None) -> list[dict]:
    """Load all patients for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of patient dicts.
    """
    data = _safe_read(_patients_file(date_str))
    return data if isinstance(data, list) else []


def save_patients(patients: list[dict], date_str: str | None = None) -> None:
    """Save all patients for a given date.

    Args:
        patients: List of patient dicts.
        date_str: Date string. Defaults to today.
    """
    _atomic_write(_patients_file(date_str), patients)


# ---------------------------------------------------------------------------
# Queue entry storage helpers
# ---------------------------------------------------------------------------


def _queue_entries_file(date_str: str | None = None) -> str:
    """Get path to the queue entries JSON file for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        Full path to queue_entries.json.
    """
    d = date_str or _today_str()
    return os.path.join(DATA_DIR, d, "queue_entries.json")


def load_queue_entries(date_str: str | None = None) -> list[dict]:
    """Load all queue entries for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of queue entry dicts.
    """
    data = _safe_read(_queue_entries_file(date_str))
    return data if isinstance(data, list) else []


def save_queue_entries(entries: list[dict], date_str: str | None = None) -> None:
    """Save all queue entries for a given date.

    Args:
        entries: List of queue entry dicts.
        date_str: Date string. Defaults to today.
    """
    _atomic_write(_queue_entries_file(date_str), entries)


# ---------------------------------------------------------------------------
# Meta / counter storage
# ---------------------------------------------------------------------------


def _meta_file(date_str: str | None = None) -> str:
    """Get path to the meta JSON file for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        Full path to meta.json.
    """
    d = date_str or _today_str()
    return os.path.join(DATA_DIR, d, "meta.json")


def _global_meta_file() -> str:
    """Get path to the global meta file (all-time references)."""
    return os.path.join(DATA_DIR, "meta.json")


def load_meta(date_str: str | None = None) -> dict:
    """Load metadata for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        Dict of metadata key-value pairs.
    """
    data = _safe_read(_meta_file(date_str))
    return data if isinstance(data, dict) else {}


def save_meta(meta: dict, date_str: str | None = None) -> None:
    """Save metadata for a given date.

    Args:
        meta: Dict of metadata key-value pairs.
        date_str: Date string. Defaults to today.
    """
    _atomic_write(_meta_file(date_str), meta)


def load_global_meta() -> dict:
    """Load global metadata (all-time references).

    Returns:
        Dict of global metadata.
    """
    data = _safe_read(_global_meta_file())
    return data if isinstance(data, dict) else {}


def save_global_meta(meta: dict) -> None:
    """Save global metadata.

    Args:
        meta: Dict of global metadata.
    """
    _atomic_write(_global_meta_file(), meta)


# ---------------------------------------------------------------------------
# Sequence number generation
# ---------------------------------------------------------------------------


def get_next_sequence(counter_key: str, date_prefix: str | None = None) -> int:
    """Get and increment a sequence counter.

    Args:
        counter_key: Name of the counter (e.g., 'patient_sequence').
        date_prefix: Date prefix for daily counters. Defaults to today.

    Returns:
        The next sequence number (1-based).
    """
    dp = date_prefix or _today_str().replace("-", "")
    meta = load_meta()
    key = f"{counter_key}_{dp}"
    current = meta.get(key, 0)
    meta[key] = current + 1
    save_meta(meta)
    return current + 1


def get_next_token_number(service_code: str, date_prefix: str | None = None) -> int:
    """Get the next sequential token number for a service today.

    Args:
        service_code: Service code (ECG, Echo, TMT, etc.).
        date_prefix: Date prefix. Defaults to today.

    Returns:
        The next token number.
    """
    return get_next_sequence(f"token_{service_code}", date_prefix)


# ---------------------------------------------------------------------------
# Date range queries
# ---------------------------------------------------------------------------


def list_date_folders() -> list[str]:
    """List all date-stamped data folders.

    Returns:
        Sorted list of date folder names (newest first).
    """
    if not os.path.exists(DATA_DIR):
        return []
    folders = [
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
        and d.replace("-", "").isdigit()
    ]
    return sorted(folders, reverse=True)


def load_all_patients() -> list[dict]:
    """Load patients from all date folders.

    Returns:
        List of all patient dicts across all dates.
    """
    all_patients = []
    for folder in list_date_folders():
        all_patients.extend(load_patients(folder))
    return all_patients


def load_all_queue_entries() -> list[dict]:
    """Load queue entries from all date folders.

    Returns:
        List of all queue entry dicts across all dates.
    """
    all_entries = []
    for folder in list_date_folders():
        all_entries.extend(load_queue_entries(folder))
    return all_entries


# ---------------------------------------------------------------------------
# Audit log storage
# ---------------------------------------------------------------------------


def _audit_file(date_str: str | None = None) -> str:
    """Get path to the audit log JSON file for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        Full path to audit_log.json.
    """
    d = date_str or _today_str()
    return os.path.join(DATA_DIR, d, "audit_log.json")


def load_audit_log(date_str: str | None = None) -> list[dict]:
    """Load audit log entries for a given date.

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of audit log entry dicts.
    """
    data = _safe_read(_audit_file(date_str))
    return data if isinstance(data, list) else []


def save_audit_log(entries: list[dict], date_str: str | None = None) -> None:
    """Save audit log entries for a given date.

    Args:
        entries: List of audit log entry dicts.
        date_str: Date string. Defaults to today.
    """
    _atomic_write(_audit_file(date_str), entries)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def check_json_health() -> bool:
    """Check if JSON storage is writable.

    Returns:
        True if the data directory is writable.
    """
    try:
        test_dir = _today_dir()
        test_file = os.path.join(test_dir, ".health_check")
        with open(test_file, "w") as f:
            f.write("ok")
        os.unlink(test_file)
        return True
    except (OSError, PermissionError):
        return False


def get_storage_stats() -> dict:
    """Get basic storage statistics.

    Returns:
        Dict with patient_count, queue_count, total_size_bytes.
    """
    total_size = 0
    patient_count = 0
    queue_count = 0

    for folder in list_date_folders():
        folder_path = os.path.join(DATA_DIR, folder)
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                total_size += os.path.getsize(fpath)
        patient_count += len(load_patients(folder))
        queue_count += len(load_queue_entries(folder))

    return {
        "backend": "json",
        "data_dir": os.path.abspath(DATA_DIR),
        "patient_count": patient_count,
        "queue_entry_count": queue_count,
        "total_size_bytes": total_size,
        "total_size_human": _human_size(total_size),
    }


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string like "1.5 MB".
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
