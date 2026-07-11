"""
Local JSON File Storage — Drop-in replacement for SQLite
==========================================================
Stores all patient & test data as human-readable JSON files
in date-stamped folders. No database setup needed.

Folder structure:
  cardioqueue_data/
    ├── 2026-07-02/
    │   ├── patients.json           # All patients registered today
    │   ├── tests_{patient_id}.json  # Tests for each patient
    │   └── counters.json            # Token counters per test type
    ├── 2026-07-03/
    │   └── ...
    └── meta.json                    # All-time references

Each patient has a sequential numeric ID per day:
  CQ-20260702-001, CQ-20260702-002, ...
"""
import json
import os
import uuid
from datetime import date, datetime
from typing import Optional

DATA_DIR = "cardioqueue_data"


def _today_dir() -> str:
    """Get today's date-stamped folder path, create if missing."""
    d = date.today().isoformat()  # 2026-07-02
    path = os.path.join(DATA_DIR, d)
    os.makedirs(path, exist_ok=True)
    return path


def _today_str() -> str:
    return date.today().isoformat()


def _now_str() -> str:
    return datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _patients_path() -> str:
    return os.path.join(_today_dir(), "patients.json")


def _load_patients() -> list[dict]:
    path = _patients_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_patients(patients: list[dict]):
    with open(_patients_path(), "w", encoding="utf-8") as f:
        json.dump(patients, f, indent=2, ensure_ascii=False)


def create_patient_json(name: str, mobile: str, age: int, gender: str) -> Optional[dict]:
    """Create a new patient record in today's JSON file.
    Returns the patient dict or None on failure."""
    patients = _load_patients()
    today = _today_str()
    now = _now_str()

    # Generate sequential patient ID
    count = len(patients)
    patient_id = f"CQ-{today.replace('-', '')}-{count + 1:03d}"

    patient = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "name": name,
        "mobile": mobile,
        "age": age,
        "gender": gender,
        "registration_date": today,
        "created_at": now
    }
    patients.append(patient)
    _save_patients(patients)
    return patient


def get_patient_by_id_json(patient_id: str) -> Optional[dict]:
    """Fetch a patient by patient_id across all date folders."""
    # Check today first
    for p in _load_patients():
        if p["patient_id"] == patient_id:
            return p
    # Check previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p["patient_id"] == patient_id:
                            return p
    return None


def get_patient_by_mobile_json(mobile: str) -> Optional[dict]:
    """Fetch the most recent patient by mobile number."""
    # Check all date folders newest first
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in reversed(patients):
                        if p["mobile"] == mobile:
                            return p
    return None


def get_today_patients_json() -> list[dict]:
    """Get all patients registered today."""
    return _load_patients()


def _get_patient_visit_count_json(mobile: str) -> int:
    """Count how many times a mobile number appears across all date folders."""
    count = 0
    if not mobile or len(mobile) != 10:
        return 0
    # Check today
    today_patients = _load_patients()
    for p in today_patients:
        if p.get("mobile") == mobile:
            count += 1
    # Check previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p.get("mobile") == mobile:
                            count += 1
    return count


def _get_patient_visits_by_mobile_json(mobile: str) -> list[dict]:
    """Fetch ALL patient records (all visits) for a mobile across all date folders."""
    results = []
    if not mobile or len(mobile) != 10:
        return results
    # Check today first
    today_patients = _load_patients()
    for p in today_patients:
        if p.get("mobile") == mobile:
            results.append(p)
    # Check previous days (newest first)
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p.get("mobile") == mobile:
                            results.append(p)
    # Sort by registration_date DESC, created_at DESC
    results.sort(key=lambda x: (x.get("registration_date", ""), x.get("created_at", "")), reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _tests_path(patient_id: str) -> str:
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    return os.path.join(_today_dir(), f"tests_{safe_id}.json")


def _all_tests_files(day_dir: str = None) -> list[str]:
    """Get all tests_*.json files in a directory."""
    dir_path = day_dir or _today_dir()
    if not os.path.exists(dir_path):
        return []
    return sorted(
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.startswith("tests_") and f.endswith(".json")
    )


def _load_tests_for_patient(patient_id: str) -> list[dict]:
    path = _tests_path(patient_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_tests_for_patient(patient_id: str, tests: list[dict]):
    with open(_tests_path(patient_id), "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2, ensure_ascii=False)


# ─── Counter for token numbers ───────────────────────────────────────────────

def _counters_path() -> str:
    return os.path.join(_today_dir(), "counters.json")


def _get_next_token(test_name: str) -> int:
    path = _counters_path()
    counters = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            counters = json.load(f)
    next_token = counters.get(test_name, 0) + 1
    counters[test_name] = next_token
    with open(path, "w", encoding="utf-8") as f:
        json.dump(counters, f, indent=2)
    return next_token


def create_test_json(patient_id: str, test_name: str, room: str) -> Optional[dict]:
    """Create a test record for a patient."""
    tests = _load_tests_for_patient(patient_id)
    now = _now_str()
    token = _get_next_token(test_name)
    queue_pos = len(tests) + 1

    test = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "test_name": test_name,
        "status": "waiting",
        "token_number": token,
        "queue_position": queue_pos,
        "room": room,
        "called_at": None,
        "started_at": None,
        "completed_at": None,
        "report_ready_at": None,
        "delivered_at": None,
        "created_at": now
    }
    tests.append(test)
    _save_tests_for_patient(patient_id, tests)
    return test


def get_tests_for_patient_json(patient_id: str) -> list[dict]:
    """Get all tests for a patient."""
    return _load_tests_for_patient(patient_id)


def get_tests_by_mobile_json(mobile: str) -> list[dict]:
    """Get all tests for a patient by mobile number."""
    patient = get_patient_by_mobile_json(mobile)
    if not patient:
        return []
    return get_tests_for_patient_json(patient["patient_id"])


def get_queue_json(test_name: str, status_filter: str = "waiting") -> list[dict]:
    """Get the queue for a test type today, joined with patient info."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}

    # Collect all tests from today
    all_tests = []
    for f in _all_tests_files():
        with open(f, "r", encoding="utf-8") as fh:
            all_tests.extend(json.load(fh))

    # Filter by test_name and status
    filtered = []
    for t in all_tests:
        if t["test_name"] != test_name:
            continue
        if status_filter and t["status"] != status_filter:
            continue
        p = patient_map.get(t["patient_id"])
        if p:
            t["patients"] = {
                "name": p["name"],
                "mobile": p["mobile"],
                "age": p["age"],
                "gender": p["gender"]
            }
            filtered.append(t)

    filtered.sort(key=lambda x: x["token_number"])
    return filtered


def update_test_status_json(test_id: str, new_status: str) -> bool:
    """Update a test's status and set the corresponding timestamp."""
    now = _now_str()
    timestamp_map = {
        "called":       "called_at",
        "in_progress":  "started_at",
        "completed":    "completed_at",
        "report_ready": "report_ready_at",
        "delivered":    "delivered_at",
    }

    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        updated = False
        for t in tests:
            if t["id"] == test_id:
                t["status"] = new_status
                if new_status in timestamp_map:
                    t[timestamp_map[new_status]] = now
                updated = True
                break
        if updated:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(tests, fh, indent=2, ensure_ascii=False)
            return True
    return False


def _save_test_notes_json(test_id: str, notes: str) -> bool:
    """Save doctor's consultation notes to a test record in JSON."""
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        updated = False
        for t in tests:
            if t["id"] == test_id:
                t["doctor_notes"] = notes
                updated = True
                break
        if updated:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(tests, fh, indent=2, ensure_ascii=False)
            return True
    return False


def get_completed_tests_json() -> list[dict]:
    """Get all tests registered today with status 'completed'."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}
    results = []
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["status"] == "completed":
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {"name": p["name"], "mobile": p["mobile"]}
                    results.append(t)
    results.sort(key=lambda x: x.get("completed_at") or "")
    return results


def get_report_ready_tests_json() -> list[dict]:
    """Get all tests with status 'report_ready'."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}
    results = []
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["status"] == "report_ready":
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {"name": p["name"], "mobile": p["mobile"]}
                    results.append(t)
    results.sort(key=lambda x: x.get("report_ready_at") or "")
    return results


def get_current_patient_json(test_name: str) -> Optional[dict]:
    """Get the patient currently being served (called or in_progress)."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}

    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["test_name"] == test_name and t["status"] in ("called", "in_progress"):
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {
                        "name": p["name"], "mobile": p["mobile"],
                        "age": p["age"], "gender": p["gender"]
                    }
                    return t
    return None


def get_department_stats_json(test_name: str) -> dict:
    """Get counts for each status for a test type (today only)."""
    stats = {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["test_name"] == test_name and t["status"] in stats:
                stats[t["status"]] += 1
    return stats


# ═══════════════════════════════════════════════════════════════════════════════════
#  ANALYTICS / AGGREGATION (cross-date, used by Reports & Analytics page)
# ═══════════════════════════════════════════════════════════════════════════════════

def _tests_files_in_range(start_date: str, end_date: str) -> list[str]:
    """Get all tests_*.json files from date folders within [start_date, end_date]."""
    files = []
    if not os.path.exists(DATA_DIR):
        return files
    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        if day < start_date or day > end_date:
            continue
        dir_path = os.path.join(DATA_DIR, day)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if fname.startswith("tests_") and fname.endswith(".json"):
                files.append(os.path.join(dir_path, fname))
    return files


def _patients_files_in_range(start_date: str, end_date: str) -> list[str]:
    """Get patients.json files from date folders within [start_date, end_date]."""
    files = []
    if not os.path.exists(DATA_DIR):
        return files
    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        if day < start_date or day > end_date:
            continue
        pfile = os.path.join(DATA_DIR, day, "patients.json")
        if os.path.exists(pfile):
            files.append(pfile)
    return files


def get_department_stats_date_range_json(test_name: str, start_date: str, end_date: str) -> dict:
    """Get status counts for a test type across a date range (JSON folder iteration)."""
    stats = {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}
    for f in _tests_files_in_range(start_date, end_date):
        try:
            tests = json.load(open(f, "r", encoding="utf-8"))
            for t in tests:
                if t.get("test_name") == test_name and t.get("status") in stats:
                    stats[t["status"]] += 1
        except Exception:
            continue
    return stats


def get_daily_patient_counts_json(days: int = 30) -> list[dict]:
    """Get patient counts per day across JSON date folders for the last N days."""
    from datetime import timedelta
    today = date.today()
    start_dt = today - timedelta(days=days - 1)
    start_str = start_dt.isoformat()
    end_str = today.isoformat()

    counts: dict[str, int] = {}
    for pf in _patients_files_in_range(start_str, end_str):
        try:
            patients = json.load(open(pf, "r", encoding="utf-8"))
            for p in patients:
                reg_date = p.get("registration_date", "")
                if start_str <= reg_date <= end_str:
                    counts[reg_date] = counts.get(reg_date, 0) + 1
        except Exception:
            continue

    return [{"date": d, "count": counts[d]} for d in sorted(counts.keys())]


def get_test_duration_stats_json(test_name: str) -> dict:
    """Calculate average durations across ALL dates for a test type (JSON)."""
    from datetime import datetime
    # We need to look at ALL date folders
    totals = {"wait_to_call": 0.0, "wait_to_start": 0.0, "wait_to_complete": 0.0}
    counts_dur = {"wait_to_call": 0, "wait_to_start": 0, "wait_to_complete": 0}

    if not os.path.exists(DATA_DIR):
        return _empty_durations_json()

    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        dir_path = os.path.join(DATA_DIR, day)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if not fname.startswith("tests_") or not fname.endswith(".json"):
                continue
            try:
                tests = json.load(open(os.path.join(dir_path, fname), "r", encoding="utf-8"))
            except Exception:
                continue
            for t in tests:
                if t.get("test_name") != test_name or t.get("status") != "completed":
                    continue
                try:
                    created = datetime.fromisoformat(t["created_at"]) if t.get("created_at") else None
                    called = datetime.fromisoformat(t["called_at"]) if t.get("called_at") else None
                    started = datetime.fromisoformat(t["started_at"]) if t.get("started_at") else None
                    completed = datetime.fromisoformat(t["completed_at"]) if t.get("completed_at") else None
                except Exception:
                    continue
                if created and called:
                    diff = (called - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_call"] += diff
                        counts_dur["wait_to_call"] += 1
                if created and started:
                    diff = (started - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_start"] += diff
                        counts_dur["wait_to_start"] += 1
                if created and completed:
                    diff = (completed - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_complete"] += diff
                        counts_dur["wait_to_complete"] += 1

    return {
        "avg_wait_to_call": round(totals["wait_to_call"] / counts_dur["wait_to_call"], 1) if counts_dur["wait_to_call"] else 0,
        "avg_wait_to_start": round(totals["wait_to_start"] / counts_dur["wait_to_start"], 1) if counts_dur["wait_to_start"] else 0,
        "avg_wait_to_complete": round(totals["wait_to_complete"] / counts_dur["wait_to_complete"], 1) if counts_dur["wait_to_complete"] else 0,
        "total_completed": counts_dur["wait_to_complete"],
    }


def _empty_durations_json() -> dict:
    return {
        "avg_wait_to_call": 0,
        "avg_wait_to_start": 0,
        "avg_wait_to_complete": 0,
        "total_completed": 0,
    }


def log_message_json(patient_id: str, mobile: str, msg_type: str, text: str,
                     sent_via: str = "none", actor: str = ""):
    """Log a message to today's messages file."""
    msgs_path = os.path.join(_today_dir(), "messages.json")
    msgs = []
    if os.path.exists(msgs_path):
        with open(msgs_path, "r", encoding="utf-8") as f:
            msgs = json.load(f)
    msgs.append({
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "mobile": mobile,
        "message_type": msg_type,
        "message_text": text,
        "sent_via": sent_via,
        "actor": actor,
        "sent_at": _now_str()
    })
    with open(msgs_path, "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=2, ensure_ascii=False)


def _get_recent_activity_json(limit: int = 50) -> list[dict]:
    """Get recent activity across all date folders (JSON fallback)."""
    all_msgs = []
    # Today first
    msgs_path = os.path.join(_today_dir(), "messages.json")
    if os.path.exists(msgs_path):
        with open(msgs_path, "r", encoding="utf-8") as f:
            all_msgs.extend(json.load(f))
    # Previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "messages.json")
            if os.path.exists(path) and day != os.path.basename(_today_dir()):
                with open(path, "r", encoding="utf-8") as f:
                    all_msgs.extend(json.load(f))
    # Sort by sent_at DESC, take limit
    all_msgs.sort(key=lambda x: x.get("sent_at", ""), reverse=True)
    # Attach patient name from patients file in same directory
    results = []
    for msg in all_msgs[:limit]:
        pid = msg.get("patient_id", "")
        pname = pid  # fallback
        # Try to find patient name from today's or any patients file
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            ppath = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(ppath):
                with open(ppath, "r", encoding="utf-8") as f:
                    for p in json.load(f):
                        if p.get("patient_id") == pid:
                            pname = p.get("name", pid)
                            break
                if pname != pid:
                    break
        msg["patient_name"] = pname
        results.append(msg)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENT ALERT SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _alert_path(patient_id: str) -> str:
    """Path to the per-patient alert flag file."""
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    # Store in today's dir — alert is ephemeral (same day)
    return os.path.join(_today_dir(), f"alert_{safe_id}.json")


def _set_patient_alert_json(patient_id: str, message: str = "") -> bool:
    """Write pending_alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        with open(alert_file, "w", encoding="utf-8") as f:
            json.dump({"pending_alert": 1, "alert_message": message, "set_at": _now_str()}, f)
        return True
    except Exception as e:
        print(f"[LocalJSON] _set_patient_alert_json error: {e}")
        return False


def _get_patient_alert_json(patient_id: str) -> dict:
    """Read pending_alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        if os.path.exists(alert_file):
            with open(alert_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("pending_alert") == 1:
                return {"has_alert": True, "message": data.get("alert_message", "")}
        return {"has_alert": False, "message": ""}
    except Exception as e:
        print(f"[LocalJSON] _get_patient_alert_json error: {e}")
        return {"has_alert": False, "message": ""}


def _clear_patient_alert_json(patient_id: str) -> bool:
    """Clear the alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        if os.path.exists(alert_file):
            os.remove(alert_file)
        return True
    except Exception as e:
        print(f"[LocalJSON] _clear_patient_alert_json error: {e}")
        return False


# ─── PATIENT INQUIRY SYSTEM (for Local JSON mode) ───────────────────────────

def _inquiry_path(patient_id: str) -> str:
    """Path to the per-patient inquiry file."""
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    return os.path.join(_today_dir(), f"inquiry_{safe_id}.json")


def set_patient_inquiry_json(patient_id: str, message: str) -> bool:
    """Set patient inquiry text (Local JSON mode)."""
    try:
        with open(_inquiry_path(patient_id), "w", encoding="utf-8") as f:
            json.dump({"inquiry": message, "set_at": _now_str()}, f)
        return True
    except Exception as e:
        print(f"[LocalJSON] set_patient_inquiry_json error: {e}")
        return False


def get_patient_inquiry_json(patient_id: str) -> str | None:
    """Get active patient inquiry text (Local JSON mode)."""
    try:
        path = _inquiry_path(patient_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("inquiry", None)
        return None
    except Exception as e:
        print(f"[LocalJSON] get_patient_inquiry_json error: {e}")
        return None


def clear_patient_inquiry_json(patient_id: str) -> bool:
    """Clear active patient inquiry (Local JSON mode)."""
    try:
        path = _inquiry_path(patient_id)
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception as e:
        print(f"[LocalJSON] clear_patient_inquiry_json error: {e}")
        return False

