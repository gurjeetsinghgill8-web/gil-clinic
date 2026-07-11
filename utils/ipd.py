"""
IPD (Inpatient Department) Module — Admissions, Beds, Wards, Discharge
======================================================================
Manages the full inpatient lifecycle: admission → bed assignment → vitals tracking → 
daily notes → discharge planning → bed release.

Tables:
    wards — Ward master data (General, Private, ICU, etc.)
    beds — Per-bed tracking with status state machine
    ipd_admissions — Core admission record linking patient to bed
    ipd_vitals — Vital signs recorded during stay
    ipd_notes — Daily progress notes by doctors/nurses

Status flow for beds: available → occupied → discharge_pending → cleaning → available
Status flow for admissions: active → discharged | transferred
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from utils.db import (
    USE_GOOGLE_SHEETS, USE_SUPABASE, USE_LOCAL_JSON, _gs_failed,
    call_gs_api, get_client, DB_FILE
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

WARD_TYPES = ["general", "private", "icu", "maternity", "pediatric", "isolation"]

BED_STATUSES = ["available", "occupied", "cleaning", "maintenance", "discharge_pending"]
BED_STATUS_ICONS = {
    "available": "🟢",
    "occupied": "🔴",
    "cleaning": "🟡",
    "maintenance": "⚪",
    "discharge_pending": "🟠",
}
BED_STATUS_LABELS = {
    "available": "Available",
    "occupied": "Occupied",
    "cleaning": "Cleaning",
    "maintenance": "Maintenance",
    "discharge_pending": "Discharge Pending",
}

ADMISSION_STATUSES = ["active", "discharged", "transferred"]
ADMISSION_SOURCES = ["opd", "emergency", "direct"]
DISCHARGE_TYPES = ["normal", "lama", "abscond", "referred", "expired"]

NOTE_TYPES = ["progress", "consultation", "instruction"]


# ─── SCHEMA INIT ──────────────────────────────────────────────────────────────

def _init_ipd_tables():
    """Create IPD tables in SQLite if they don't exist."""
    if USE_SUPABASE or USE_GOOGLE_SHEETS:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ward_type TEXT NOT NULL DEFAULT 'general',
                total_beds INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS beds (
                id TEXT PRIMARY KEY,
                ward_id TEXT NOT NULL,
                bed_label TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                last_cleaned TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ward_id) REFERENCES wards(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ipd_admissions (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'direct',
                admitting_doctor TEXT DEFAULT '',
                diagnosis_primary TEXT DEFAULT '',
                diagnosis_secondary TEXT DEFAULT '',
                assigned_bed_id TEXT,
                admission_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                discharge_date TEXT,
                discharge_type TEXT,
                discharge_summary TEXT DEFAULT '',
                follow_up_date TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                FOREIGN KEY (assigned_bed_id) REFERENCES beds(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ipd_vitals (
                id TEXT PRIMARY KEY,
                admission_id TEXT NOT NULL,
                bp_systolic INTEGER DEFAULT 0,
                bp_diastolic INTEGER DEFAULT 0,
                pulse INTEGER DEFAULT 0,
                temperature REAL DEFAULT 0.0,
                spo2 INTEGER DEFAULT 0,
                weight REAL DEFAULT 0.0,
                recorded_at TEXT NOT NULL,
                recorded_by TEXT DEFAULT '',
                FOREIGN KEY (admission_id) REFERENCES ipd_admissions(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ipd_notes (
                id TEXT PRIMARY KEY,
                admission_id TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                notes TEXT NOT NULL,
                note_type TEXT NOT NULL DEFAULT 'progress',
                created_at TEXT NOT NULL,
                FOREIGN KEY (admission_id) REFERENCES ipd_admissions(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

        # Seed default wards and beds
        _seed_default_wards(cursor, conn)
    except Exception as e:
        print(f"[IPDDB] init error: {e}")
    finally:
        conn.close()


def _seed_default_wards(cursor, conn):
    """Create default wards and beds if none exist."""
    try:
        cursor.execute("SELECT COUNT(*) FROM wards")
        if cursor.fetchone()[0] > 0:
            return

        now_str = datetime.now().isoformat()
        default_wards = [
            ("General Ward", "general", 10, "General medicine ward"),
            ("Private Wing", "private", 6, "Private rooms with attached bathroom"),
            ("ICU", "icu", 4, "Intensive Care Unit — cardiac monitoring"),
        ]

        for wname, wtype, beds_count, desc in default_wards:
            wid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO wards (id, name, ward_type, total_beds, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (wid, wname, wtype, beds_count, desc, now_str)
            )
            # Create beds for this ward
            for i in range(1, beds_count + 1):
                bid = str(uuid.uuid4())
                label = f"Bed-{i:02d}"
                prefix = {"general": "G", "private": "P", "icu": "I"}.get(wtype, "W")
                cursor.execute(
                    "INSERT INTO beds (id, ward_id, bed_label, status, is_active, created_at) VALUES (?, ?, ?, 'available', 1, ?)",
                    (bid, wid, f"{prefix}-{i:02d} {label}", now_str)
                )
        conn.commit()
        print(f"[IPDDB] Seeded {len(default_wards)} wards with beds.")
    except Exception as e:
        print(f"[IPDDB] seed error: {e}")


# Initialize on import
_init_ipd_tables()


# ═══════════════════════════════════════════════════════════════════════════════
#  WARDS & BEDS
# ═══════════════════════════════════════════════════════════════════════════════

def get_wards(active_only: bool = True) -> list[dict]:
    """Get all wards."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_wards_json(active_only)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM wards"
        params = []
        if active_only:
            query += " WHERE is_active=1"
        query += " ORDER BY ward_type, name"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[IPDDB] get_wards error: {e}")
        return []
    finally:
        conn.close()


def get_beds_for_ward(ward_id: str, status: str = "") -> list[dict]:
    """Get all beds in a ward, optionally filtered by status."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_beds_for_ward_json(ward_id, status)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM beds WHERE ward_id=? AND is_active=1"
        params = [ward_id]
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY bed_label"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[IPDDB] get_beds error: {e}")
        return []
    finally:
        conn.close()


def get_ward_occupancy() -> list[dict]:
    """
    Get occupancy summary for all wards.
    Returns: [{ward_id, name, ward_type, total_beds, available, occupied, cleaning, maintenance}]
    """
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_ward_occupancy_json()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT w.id, w.name, w.ward_type, w.total_beds,
                   SUM(CASE WHEN b.status='available' THEN 1 ELSE 0 END) AS available,
                   SUM(CASE WHEN b.status='occupied' THEN 1 ELSE 0 END) AS occupied,
                   SUM(CASE WHEN b.status='cleaning' THEN 1 ELSE 0 END) AS cleaning,
                   SUM(CASE WHEN b.status IN ('maintenance','discharge_pending') THEN 1 ELSE 0 END) AS other
            FROM wards w
            LEFT JOIN beds b ON b.ward_id = w.id AND b.is_active=1
            WHERE w.is_active=1
            GROUP BY w.id
            ORDER BY w.ward_type, w.name
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[IPDDB] get_occupancy error: {e}")
        return []
    finally:
        conn.close()


def update_bed_status(bed_id: str, new_status: str) -> bool:
    """Update a bed's status."""
    if new_status not in BED_STATUSES:
        return False
    json_mod = _get_json()
    if json_mod:
        return json_mod.update_bed_status_json(bed_id, new_status)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        now_str = datetime.now().isoformat()
        if new_status == "available":
            cursor.execute("UPDATE beds SET status=?, last_cleaned=? WHERE id=?",
                           (new_status, now_str, bed_id))
        else:
            cursor.execute("UPDATE beds SET status=? WHERE id=?",
                           (new_status, bed_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def get_available_beds(ward_id: str = "") -> list[dict]:
    """Get all available beds, optionally filtered by ward."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_available_beds_json(ward_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT b.*, w.name AS ward_name, w.ward_type FROM beds b JOIN wards w ON b.ward_id=w.id WHERE b.status='available' AND b.is_active=1"
        params = []
        if ward_id:
            query += " AND b.ward_id=?"
            params.append(ward_id)
        query += " ORDER BY w.ward_type, b.bed_label"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def admit_patient(patient_id: str, patient_name: str, mobile: str,
                  source: str = "direct", admitting_doctor: str = "",
                  diagnosis_primary: str = "", diagnosis_secondary: str = "",
                  bed_id: str = "", notes: str = "") -> dict:
    """
    Admit a patient to IPD.

    Args:
        patient_id: Patient's public ID
        patient_name: Patient's name
        mobile: 10-digit mobile
        source: opd/emergency/direct
        admitting_doctor: Doctor's display name
        diagnosis_primary: Primary diagnosis
        diagnosis_secondary: Secondary diagnosis (optional)
        bed_id: Bed UUID to assign
        notes: Additional admission notes

    Returns:
        dict with "success" bool, "message" string, and optionally "admission" dict
    """
    if source not in ADMISSION_SOURCES:
        return {"success": False, "message": f"Invalid source. Choose from: {', '.join(ADMISSION_SOURCES)}"}

    # Validate bed if provided
    if bed_id:
        json_mod = _get_json()
        if json_mod:
            beds = json_mod.get_beds_json()
            bed = next((b for b in beds if b["id"] == bed_id), None)
            if not bed:
                return {"success": False, "message": "❌ Bed not found."}
            if bed.get("status") != "available":
                return {"success": False, "message": "❌ Bed is not available."}
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT status FROM beds WHERE id=?", (bed_id,))
                bed = cursor.fetchone()
                if not bed:
                    return {"success": False, "message": "❌ Bed not found."}
                if bed[0] != "available":
                    return {"success": False, "message": "❌ Bed is not available."}
            except Exception as e:
                return {"success": False, "message": f"❌ Database error: {e}"}
            finally:
                conn.close()

    now_str = datetime.now().isoformat()
    admission_id = str(uuid.uuid4())
    today_str = date.today().isoformat()

    # ─── Google Sheets ────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("admitPatient", {
            "id": admission_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "source": source,
            "admitting_doctor": admitting_doctor,
            "diagnosis_primary": diagnosis_primary,
            "diagnosis_secondary": diagnosis_secondary,
            "assigned_bed_id": bed_id,
            "admission_date": today_str,
            "notes": notes,
            "created_at": now_str,
        }, is_post=True)
        if res:
            if bed_id:
                update_bed_status(bed_id, "occupied")
            return {"success": True, "message": f"✅ {patient_name} admitted successfully!", "admission": res}
        # Fall through to Local JSON

    # ─── Local JSON ───────────────────────────────────────────────────────────
    json_mod = _get_json()
    if json_mod:
        result = json_mod.admit_patient_json(
            patient_id, patient_name, mobile, source, admitting_doctor,
            diagnosis_primary, diagnosis_secondary, bed_id, notes
        )
        if result["success"] and bed_id:
            update_bed_status(bed_id, "occupied")
        return result

    # ─── SQLite / Supabase ────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            data = {
                "id": admission_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "mobile": mobile,
                "source": source,
                "admitting_doctor": admitting_doctor,
                "diagnosis_primary": diagnosis_primary,
                "diagnosis_secondary": diagnosis_secondary,
                "assigned_bed_id": bed_id,
                "admission_date": today_str,
                "notes": notes,
                "created_at": now_str,
            }
            get_client().table("ipd_admissions").insert(data).execute()
            if bed_id:
                update_bed_status(bed_id, "occupied")
            return {"success": True, "message": f"✅ {patient_name} admitted successfully!", "admission": data}
        except Exception as e:
            print(f"[IPDDB] Supabase error: {e}")
            return {"success": False, "message": "❌ Failed to admit patient."}
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO ipd_admissions (id, patient_id, patient_name, mobile, source, "
                "admitting_doctor, diagnosis_primary, diagnosis_secondary, assigned_bed_id, "
                "admission_date, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (admission_id, patient_id, patient_name, mobile, source,
                 admitting_doctor, diagnosis_primary, diagnosis_secondary,
                 bed_id, today_str, notes, now_str)
            )
            conn.commit()
            if bed_id:
                update_bed_status(bed_id, "occupied")
            return {
                "success": True,
                "message": f"✅ {patient_name} admitted successfully!",
                "admission": {
                    "id": admission_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "mobile": mobile,
                    "source": source,
                    "admitting_doctor": admitting_doctor,
                    "diagnosis_primary": diagnosis_primary,
                    "diagnosis_secondary": diagnosis_secondary,
                    "assigned_bed_id": bed_id,
                    "admission_date": today_str,
                    "status": "active",
                    "notes": notes,
                    "created_at": now_str,
                }
            }
        except Exception as e:
            print(f"[IPDDB] SQLite error: {e}")
            return {"success": False, "message": "❌ Failed to admit patient."}
        finally:
            conn.close()


def discharge_patient(admission_id: str, discharge_type: str = "normal",
                      discharge_summary: str = "", follow_up_date: str = "") -> dict:
    """
    Discharge a patient. Releases the bed after marking discharge_pending.

    Args:
        admission_id: Admission record UUID
        discharge_type: normal/lama/abscond/referred/expired
        discharge_summary: Clinical summary at discharge
        follow_up_date: Optional follow-up appointment date

    Returns:
        dict with "success" bool and "message" string
    """
    if discharge_type not in DISCHARGE_TYPES:
        return {"success": False, "message": f"Invalid discharge type. Choose from: {', '.join(DISCHARGE_TYPES)}"}

    json_mod = _get_json()
    if json_mod:
        return json_mod.discharge_patient_json(admission_id, discharge_type, discharge_summary, follow_up_date)

    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Get admission record
        cursor.execute("SELECT assigned_bed_id FROM ipd_admissions WHERE id=? AND status='active'",
                       (admission_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "❌ Active admission not found."}

        bed_id = row[0]

        # Update admission record
        cursor.execute(
            "UPDATE ipd_admissions SET status='discharged', discharge_type=?, "
            "discharge_summary=?, discharge_date=?, follow_up_date=? WHERE id=?",
            (discharge_type, discharge_summary, now_str, follow_up_date or None, admission_id)
        )

        # Mark bed as discharge_pending → will be cleaned manually
        if bed_id:
            cursor.execute("UPDATE beds SET status='discharge_pending' WHERE id=?", (bed_id,))

        conn.commit()
        return {"success": True, "message": f"✅ Patient discharged ({discharge_type}). Bed marked for cleaning."}
    except Exception as e:
        print(f"[IPDDB] discharge error: {e}")
        return {"success": False, "message": "❌ Failed to discharge patient."}
    finally:
        conn.close()


def get_active_admissions(ward_id: str = "") -> list[dict]:
    """Get all active admissions, optionally filtered by ward."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_active_admissions_json(ward_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT a.*, b.bed_label, w.name AS ward_name, w.ward_type
            FROM ipd_admissions a
            LEFT JOIN beds b ON a.assigned_bed_id = b.id
            LEFT JOIN wards w ON b.ward_id = w.id
            WHERE a.status='active'
        """
        params = []
        if ward_id:
            query += " AND w.id=?"
            params.append(ward_id)
        query += " ORDER BY a.admission_date DESC, a.created_at ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[IPDDB] get_active error: {e}")
        return []
    finally:
        conn.close()


def get_discharged_patients(limit: int = 50, ward_id: str = "") -> list[dict]:
    """Get recently discharged patients."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_discharged_patients_json(limit, ward_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT a.*, b.bed_label, w.name AS ward_name, w.ward_type
            FROM ipd_admissions a
            LEFT JOIN beds b ON a.assigned_bed_id = b.id
            LEFT JOIN wards w ON b.ward_id = w.id
            WHERE a.status='discharged'
        """
        params = []
        if ward_id:
            query += " AND w.id=?"
            params.append(ward_id)
        query += " ORDER BY a.discharge_date DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_ipd_patient_status(patient_id: str) -> dict | None:
    """Get active admission for a patient. Returns None if not admitted."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_ipd_patient_status_json(patient_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT a.*, b.bed_label, w.name AS ward_name, w.ward_type
            FROM ipd_admissions a
            LEFT JOIN beds b ON a.assigned_bed_id = b.id
            LEFT JOIN wards w ON b.ward_id = w.id
            WHERE a.patient_id=? AND a.status='active'
            LIMIT 1
        """, (patient_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    except Exception:
        return None
    finally:
        conn.close()


def get_patient_admission_history(patient_id: str) -> list[dict]:
    """Get all admissions (past and present) for a patient."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_patient_admission_history_json(patient_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT a.*, b.bed_label, w.name AS ward_name
            FROM ipd_admissions a
            LEFT JOIN beds b ON a.assigned_bed_id = b.id
            LEFT JOIN wards w ON b.ward_id = w.id
            WHERE a.patient_id=?
            ORDER BY a.created_at DESC
        """, (patient_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  VITALS
# ═══════════════════════════════════════════════════════════════════════════════

def record_vitals(admission_id: str, bp_systolic: int = 0, bp_diastolic: int = 0,
                  pulse: int = 0, temperature: float = 0.0, spo2: int = 0,
                  weight: float = 0.0, recorded_by: str = "") -> dict:
    """Record vital signs for an admitted patient."""
    now_str = datetime.now().isoformat()
    vitals_id = str(uuid.uuid4())

    json_mod = _get_json()
    if json_mod:
        return json_mod.record_vitals_json(
            admission_id, bp_systolic, bp_diastolic, pulse, temperature, spo2, weight, recorded_by
        )

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ipd_vitals (id, admission_id, bp_systolic, bp_diastolic, pulse, "
            "temperature, spo2, weight, recorded_at, recorded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vitals_id, admission_id, bp_systolic, bp_diastolic, pulse,
             temperature, spo2, weight, now_str, recorded_by)
        )
        conn.commit()
        return {"success": True, "message": "✅ Vitals recorded."}
    except Exception as e:
        print(f"[IPDDB] vitals error: {e}")
        return {"success": False, "message": "❌ Failed to record vitals."}
    finally:
        conn.close()


def get_vitals_for_admission(admission_id: str, limit: int = 20) -> list[dict]:
    """Get vitals history for an admission."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_vitals_for_admission_json(admission_id, limit)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM ipd_vitals WHERE admission_id=? ORDER BY recorded_at DESC LIMIT ?",
            (admission_id, limit)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  NOTES
# ═══════════════════════════════════════════════════════════════════════════════

def add_ipd_note(admission_id: str, doctor_name: str, notes: str,
                 note_type: str = "progress") -> dict:
    """Add a clinical note for an admitted patient."""
    if note_type not in NOTE_TYPES:
        return {"success": False, "message": f"Invalid note type. Choose from: {', '.join(NOTE_TYPES)}"}
    now_str = datetime.now().isoformat()
    note_id = str(uuid.uuid4())

    json_mod = _get_json()
    if json_mod:
        return json_mod.add_ipd_note_json(admission_id, doctor_name, notes, note_type)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ipd_notes (id, admission_id, doctor_name, notes, note_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (note_id, admission_id, doctor_name, notes, note_type, now_str)
        )
        conn.commit()
        return {"success": True, "message": "📝 Note added."}
    except Exception as e:
        print(f"[IPDDB] notes error: {e}")
        return {"success": False, "message": "❌ Failed to add note."}
    finally:
        conn.close()


def get_notes_for_admission(admission_id: str, limit: int = 50) -> list[dict]:
    """Get clinical notes for an admission."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_notes_for_admission_json(admission_id, limit)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM ipd_notes WHERE admission_id=? ORDER BY created_at DESC LIMIT ?",
            (admission_id, limit)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def generate_discharge_summary(admission_id: str) -> dict:
    """Generate discharge summary for an IPD patient."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ipd_admissions WHERE id=?", (admission_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Admission not found"}
        columns = [desc[0] for desc in cursor.description]
        admission = dict(zip(columns, row))

        # Update status
        cursor.execute("UPDATE ipd_admissions SET status='discharged', discharged_at=? WHERE id=?",
                      (datetime.now().isoformat(), admission_id))
        conn.commit()

        summary = {
            "patient_name": admission.get("patient_name", ""),
            "admission_date": admission.get("admitted_at", "")[:10] if admission.get("admitted_at") else "",
            "discharge_date": datetime.now().strftime("%Y-%m-%d"),
            "diagnosis": admission.get("diagnosis", ""),
            "doctor": admission.get("admitted_by", ""),
            "ward": admission.get("ward_type", ""),
        }
        return {"success": True, "summary": summary, "message": "✅ Discharge summary generated"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
