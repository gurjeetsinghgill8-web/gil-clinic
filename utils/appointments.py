"""
Appointments Module — Scheduling & Time Slot Management
========================================================
DB operations for appointment booking with time slots.

Tables:
    appointments — Individual appointments (patient, test, date, time, status)
    time_slots — Configurable time slots per department
    appointment_reminders — Log of sent reminders

Status flow: scheduled → checked_in → in_progress → completed | cancelled
"""
import uuid
from datetime import date, datetime, timedelta, time as dt_time
from typing import Optional

from utils.db import (
    USE_GOOGLE_SHEETS, USE_SUPABASE, USE_LOCAL_JSON, _gs_failed,
    call_gs_api, get_client, DB_FILE, get_patient_by_mobile
)
import sqlite3

# ─── JSON fallback (lazy import) ──────────────────────────────────────────────
_json_module = None


def _get_json():
    global _json_module
    if _json_module is None and USE_LOCAL_JSON:
        from utils import local_json_db
        _json_module = local_json_db
    return _json_module


# ─── CONSTANTS ─────────────────────────────────────────────────────────────────

APPOINTMENT_STATUSES = ["scheduled", "checked_in", "in_progress", "completed", "cancelled"]
APPOINTMENT_STATUS_ICONS = {
    "scheduled": "📅",
    "checked_in": "✅",
    "in_progress": "🟠",
    "completed": "🟢",
    "cancelled": "❌",
}

# Default slot configuration (15 min slots)
DEFAULT_SLOT_DURATION = 15  # minutes
DEFAULT_START_HOUR = 9  # 9 AM
DEFAULT_END_HOUR = 17  # 5 PM
DEFAULT_MAX_PER_SLOT = 3  # patients per 15-min slot


# ─── SCHEMA INIT ──────────────────────────────────────────────────────────────

def _init_appointment_tables():
    """Create appointment tables in SQLite if they don't exist."""
    if USE_SUPABASE or USE_GOOGLE_SHEETS:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                test_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_slots (
                id TEXT PRIMARY KEY,
                test_name TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                max_per_slot INTEGER NOT NULL DEFAULT 3,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(test_name, slot_time)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointment_reminders (
                id TEXT PRIMARY KEY,
                appointment_id TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[ApptDB] init error: {e}")
    finally:
        conn.close()


# Initialize on import
_init_appointment_tables()


# ─── TIME SLOT MANAGEMENT ─────────────────────────────────────────────────────

def generate_default_slots(test_name: str) -> list[str]:
    """Generate default 15-min time slots for a given test type."""
    slots = []
    current = datetime.now().replace(hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0)
    end = datetime.now().replace(hour=DEFAULT_END_HOUR, minute=0, second=0, microsecond=0)
    while current < end:
        slots.append(current.strftime("%I:%M %p").lstrip("0"))
        current += timedelta(minutes=DEFAULT_SLOT_DURATION)
    return slots


def ensure_slots_for_test(test_name: str):
    """Ensure default time slots exist for a test type."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Check if slots exist
        cursor.execute("SELECT COUNT(*) FROM time_slots WHERE test_name=? AND active=1", (test_name,))
        count = cursor.fetchone()[0]
        if count > 0:
            return  # Slots already exist

        slots = generate_default_slots(test_name)
        for slot in slots:
            sid = str(uuid.uuid4())
            cursor.execute(
                "INSERT OR IGNORE INTO time_slots (id, test_name, slot_time, max_per_slot) VALUES (?, ?, ?, ?)",
                (sid, test_name, slot, DEFAULT_MAX_PER_SLOT)
            )
        conn.commit()
        print(f"[ApptDB] Created {len(slots)} slots for {test_name}")
    except Exception as e:
        print(f"[ApptDB] ensure_slots error: {e}")
    finally:
        conn.close()


def get_available_slots(test_name: str, appt_date: Optional[str] = None) -> list[dict]:
    """
    Get available time slots for a test on a given date.
    Returns slots with their capacity and current booking count.
    """
    if appt_date is None:
        appt_date = date.today().isoformat()

    # Ensure slots exist
    ensure_slots_for_test(test_name)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Get all active slots for this test
        cursor.execute(
            "SELECT id, slot_time, max_per_slot FROM time_slots WHERE test_name=? AND active=1 ORDER BY slot_time",
            (test_name,)
        )
        slots = cursor.fetchall()

        # Get current booking count for each slot on this date
        result = []
        for slot_id, slot_time, max_per_slot in slots:
            cursor.execute(
                "SELECT COUNT(*) FROM appointments WHERE test_name=? AND appointment_date=? AND time_slot=? AND status NOT IN ('cancelled')",
                (test_name, appt_date, slot_time)
            )
            booked = cursor.fetchone()[0]
            available = max_per_slot - booked
            result.append({
                "id": slot_id,
                "time": slot_time,
                "max_per_slot": max_per_slot,
                "booked": booked,
                "available": max(0, available),
                "is_full": available <= 0,
            })
        return result
    except Exception as e:
        print(f"[ApptDB] get_available_slots error: {e}")
        return []
    finally:
        conn.close()


# ─── APPOINTMENT CRUD ──────────────────────────────────────────────────────────

def book_appointment(patient_id: str, patient_name: str, mobile: str,
                     test_name: str, appt_date: str, time_slot: str,
                     notes: str = "") -> dict:
    """
    Book a new appointment.

    Args:
        patient_id: Patient's public ID
        patient_name: Patient's name
        mobile: 10-digit mobile
        test_name: e.g. ECG, Echo, TMT, OPD
        appt_date: ISO date string (YYYY-MM-DD)
        time_slot: e.g. "10:30 AM"
        notes: Optional notes

    Returns:
        dict with "success" bool, "message" string, and optionally "appointment" dict
    """
    # Validate date is not in the past
    try:
        appt_dt = datetime.strptime(appt_date, "%Y-%m-%d").date()
        if appt_dt < date.today():
            return {"success": False, "message": "❌ Cannot book appointments in the past."}
    except ValueError:
        return {"success": False, "message": "❌ Invalid date format. Use YYYY-MM-DD."}

    # Check slot availability
    slots = get_available_slots(test_name, appt_date)
    selected_slot = next((s for s in slots if s["time"] == time_slot), None)
    if not selected_slot:
        return {"success": False, "message": f"❌ Time slot '{time_slot}' not found for {test_name}."}
    if selected_slot["is_full"]:
        return {"success": False, "message": f"❌ Time slot '{time_slot}' is fully booked."}

    now_str = datetime.now().isoformat()
    appt_id = str(uuid.uuid4())

    # ─── Google Sheets ────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("bookAppointment", {
            "id": appt_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "test_name": test_name,
            "appointment_date": appt_date,
            "time_slot": time_slot,
            "notes": notes,
            "created_at": now_str,
            "updated_at": now_str,
        }, is_post=True)
        if res:
            return {"success": True, "message": f"✅ Appointment booked for {appt_date} at {time_slot}", "appointment": res}
        # Fall through to Local JSON

    # ─── Local JSON ───────────────────────────────────────────────────────────
    json_mod = _get_json()
    if json_mod:
        return json_mod.book_appointment_json(patient_id, patient_name, mobile, test_name, appt_date, time_slot, notes)

    # ─── SQLite / Supabase ────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            data = {
                "id": appt_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "mobile": mobile,
                "test_name": test_name,
                "appointment_date": appt_date,
                "time_slot": time_slot,
                "notes": notes,
                "created_at": now_str,
                "updated_at": now_str,
            }
            get_client().table("appointments").insert(data).execute()
            return {
                "success": True,
                "message": f"✅ Appointment booked for {appt_date} at {time_slot}",
                "appointment": data
            }
        except Exception as e:
            print(f"[ApptDB] Supabase error: {e}")
            return {"success": False, "message": "❌ Failed to book appointment."}
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO appointments (id, patient_id, patient_name, mobile, test_name, "
                "appointment_date, time_slot, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (appt_id, patient_id, patient_name, mobile, test_name,
                 appt_date, time_slot, notes, now_str, now_str)
            )
            conn.commit()
            return {
                "success": True,
                "message": f"✅ Appointment booked for {appt_date} at {time_slot}",
                "appointment": {
                    "id": appt_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "mobile": mobile,
                    "test_name": test_name,
                    "appointment_date": appt_date,
                    "time_slot": time_slot,
                    "notes": notes,
                    "status": "scheduled",
                    "created_at": now_str,
                }
            }
        except Exception as e:
            print(f"[ApptDB] SQLite error: {e}")
            return {"success": False, "message": "❌ Failed to book appointment."}
        finally:
            conn.close()


def get_appointments_for_date(appt_date: Optional[str] = None,
                              test_name: str = "") -> list[dict]:
    """
    Get all appointments for a given date, optionally filtered by test.
    Ordered by time_slot.
    """
    if appt_date is None:
        appt_date = date.today().isoformat()

    json_mod = _get_json()
    if json_mod:
        return json_mod.get_appointments_for_date_json(appt_date, test_name)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM appointments WHERE appointment_date=?"
        params = [appt_date]
        if test_name:
            query += " AND test_name=?"
            params.append(test_name)
        query += " ORDER BY time_slot"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[ApptDB] get_appointments error: {e}")
        return []
    finally:
        conn.close()


def get_appointments_for_patient(mobile: str) -> list[dict]:
    """Get all appointments for a patient by mobile number."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_appointments_for_patient_json(mobile)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM appointments WHERE mobile=? ORDER BY appointment_date DESC, time_slot",
            (mobile,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def update_appointment_status(appt_id: str, new_status: str) -> bool:
    """Update appointment status (scheduled → checked_in → in_progress → completed | cancelled)."""
    if new_status not in APPOINTMENT_STATUSES:
        return False

    json_mod = _get_json()
    if json_mod:
        return json_mod.update_appointment_status_json(appt_id, new_status)

    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE appointments SET status=?, updated_at=? WHERE id=?",
            (new_status, now_str, appt_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def cancel_appointment(appt_id: str, reason: str = "") -> bool:
    """Cancel an appointment."""
    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE appointments SET status='cancelled', notes=CASE WHEN ?!='' THEN ? ELSE notes END, updated_at=? WHERE id=?",
            (reason, reason, now_str, appt_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def get_today_appointments_count(test_name: str = "") -> int:
    """Get number of scheduled appointments for today."""
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND status NOT IN ('cancelled')"
        params = [today]
        if test_name:
            query += " AND test_name=?"
            params.append(test_name)
        cursor.execute(query, params)
        return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()
