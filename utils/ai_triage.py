"""
AI Triage — Symptom Assessment & Severity Classification
===========================================================
Rule-based triage engine: 5-level severity, red-flag detection,
department recommendation, ICD-10 mapping.
"""
import uuid
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

TRIAGE_LEVELS = {
    "1-Emergency": {"label": "🚨 Emergency", "wait_time": "0 min", "color": "#FF5722"},
    "2-Urgent": {"label": "🔴 Urgent", "wait_time": "< 4 hours", "color": "#FF9800"},
    "3-Moderate": {"label": "🟡 Moderate", "wait_time": "< 24 hours", "color": "#FFC107"},
    "4-Mild": {"label": "🟢 Mild", "wait_time": "< 72 hours", "color": "#4CAF50"},
    "5-Self-care": {"label": "⚪ Self-care", "wait_time": "Home care", "color": "#9E9E9E"},
}

RED_FLAGS = [
    "chest pain", "difficulty breathing", "shortness of breath", "unconscious",
    "severe bleeding", "head injury", "stroke symptoms", "paralysis",
    "seizure", "suicidal", "anaphylaxis", "blue lips", "choking",
    "severe burn", "snake bite", "poisoning", "overdose",
]

SYMPTOM_DEPT_MAP = {
    "chest pain": "Cardiology", "palpitations": "Cardiology",
    "fever": "General Medicine", "cough": "General Medicine",
    "abdominal pain": "Gastroenterology", "headache": "Neurology",
    "joint pain": "Orthopedics", "skin rash": "Dermatology",
    "back pain": "Orthopedics", "dizziness": "Neurology",
    "urinary": "Urology", "eye": "Ophthalmology",
    "ear": "ENT", "throat": "ENT", "dental": "Dentist",
}

ICD10_MAP = {
    "chest pain": "R07.9", "hypertension": "I10", "fever": "R50.9",
    "diabetes": "E11.9", "headache": "R51", "cough": "R05",
    "abdominal pain": "R10.9", "back pain": "M54.9", "dizziness": "R42",
    "shortness of breath": "R06.0", "palpitations": "R00.2",
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_assessments (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                age INTEGER, gender TEXT, chief_complaint TEXT NOT NULL,
                symptoms TEXT DEFAULT '', severity TEXT NOT NULL,
                recommended_dept TEXT DEFAULT '', icd10_code TEXT DEFAULT '',
                confidence REAL DEFAULT 0.8, red_flags TEXT DEFAULT '',
                is_escalated INTEGER DEFAULT 0, created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_questions (
                id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL,
                question TEXT NOT NULL, answer TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (assessment_id) REFERENCES triage_assessments(id)
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def assess_symptoms(chief_complaint: str, symptoms: str = "",
                    patient_name: str = "", age: int = 0, gender: str = "",
                    patient_id: str = "") -> dict:
    """Run rule-based triage assessment."""
    cc_lower = chief_complaint.lower()
    sym_lower = symptoms.lower()
    combined = cc_lower + " " + sym_lower

    # 1. Check red flags
    detected_red_flags = [rf for rf in RED_FLAGS if rf in combined]
    if detected_red_flags:
        severity = "1-Emergency"
        confidence = 0.95
        is_escalated = 1
    else:
        # 2. Severity scoring
        score = 0
        severity_keywords = {
            "severe": 3, "worst": 3, "unbearable": 3, "cannot move": 3,
            "heavy": 2, "persistent": 2, "recurring": 2, "chronic": 1,
            "mild": -1, "slight": -1, "occasional": -1,
        }
        for kw, pts in severity_keywords.items():
            if kw in combined:
                score += pts

        # Age risk factor
        if age > 60 or age < 5:
            score += 1

        if score >= 4:
            severity = "2-Urgent"
        elif score >= 2:
            severity = "3-Moderate"
        elif score >= 0:
            severity = "4-Mild"
        else:
            severity = "5-Self-care"
        confidence = min(0.9, 0.5 + (len(combined) / 500))
        is_escalated = 1 if severity in ("1-Emergency", "2-Urgent") else 0

    # 3. Department recommendation
    recommended_dept = "General Medicine"
    for keyword, dept in SYMPTOM_DEPT_MAP.items():
        if keyword in combined:
            recommended_dept = dept
            break

    # 4. ICD-10 mapping
    icd10 = ""
    for keyword, code in ICD10_MAP.items():
        if keyword in combined:
            icd10 = code
            break

    # 5. Save assessment
    aid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO triage_assessments (id, patient_id, patient_name, age, gender, "
            "chief_complaint, symptoms, severity, recommended_dept, icd10_code, "
            "confidence, red_flags, is_escalated, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, patient_id or "", patient_name, age, gender,
             chief_complaint, symptoms, severity, recommended_dept, icd10_code,
             confidence, ", ".join(detected_red_flags), is_escalated, now)
        )
        conn.commit()
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()

    return {
        "success": True,
        "assessment_id": aid,
        "severity": severity,
        "severity_info": TRIAGE_LEVELS.get(severity, {}),
        "confidence": confidence,
        "recommended_dept": recommended_dept,
        "icd10_code": icd10,
        "red_flags": detected_red_flags,
        "is_escalated": bool(is_escalated),
        "message": f"Assessment complete. Severity: {severity}",
    }


def get_triage_history(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM triage_assessments ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_triage_stats() -> dict:
    conn = sqlite3.connect(DB_FILE)
    try:
        total = conn.execute("SELECT COUNT(*) FROM triage_assessments").fetchone()[0]
        emergency = conn.execute("SELECT COUNT(*) FROM triage_assessments WHERE severity='1-Emergency'").fetchone()[0]
        escalated = conn.execute("SELECT COUNT(*) FROM triage_assessments WHERE is_escalated=1").fetchone()[0]
        return {"total": total, "emergency": emergency, "escalated": escalated}
    except Exception:
        return {"total": 0, "emergency": 0, "escalated": 0}
    finally:
        conn.close()
