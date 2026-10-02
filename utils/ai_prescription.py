"""
AI Prescription Assistant — Medicine Suggestions, Drug Interaction Check
==========================================================================
"""
import uuid
import json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

# Medicine database (common cardiac + general)
MEDICINE_DB = {
    "Aspirin": {"category": "antiplatelet", "dosage": "75-325mg", "interactions": ["Warfarin", "Clopidogrel"]},
    "Clopidogrel": {"category": "antiplatelet", "dosage": "75mg", "interactions": ["Aspirin", "Omeprazole"]},
    "Atorvastatin": {"category": "statin", "dosage": "10-80mg", "interactions": ["Clarithromycin", "Grapefruit"]},
    "Rosuvastatin": {"category": "statin", "dosage": "5-40mg", "interactions": ["Warfarin"]},
    "Metoprolol": {"category": "beta_blocker", "dosage": "25-100mg", "interactions": ["Verapamil", "Digoxin"]},
    "Amlodipine": {"category": "CCB", "dosage": "2.5-10mg", "interactions": ["Simvastatin"]},
    "Enalapril": {"category": "ACE_inhibitor", "dosage": "2.5-20mg", "interactions": ["K_sparing_diuretics", "ARBs"]},
    "Losartan": {"category": "ARB", "dosage": "25-100mg", "interactions": ["Enalapril", "K_supplements"]},
    "Furosemide": {"category": "diuretic", "dosage": "20-80mg", "interactions": ["Digoxin", "NSAIDs"]},
    "Digoxin": {"category": "cardiac_glycoside", "dosage": "0.125-0.25mg", "interactions": ["Furosemide", "Amiodarone"]},
    "Warfarin": {"category": "anticoagulant", "dosage": "1-10mg", "interactions": ["Aspirin", "NSAIDs"]},
    "Metformin": {"category": "antidiabetic", "dosage": "500-2000mg", "interactions": ["Contrast_dye", "Alcohol"]},
    "Omeprazole": {"category": "PPI", "dosage": "20-40mg", "interactions": ["Clopidogrel", "Digoxin"]},
    "Paracetamol": {"category": "analgesic", "dosage": "500-1000mg", "interactions": ["Warfarin"]},
    "Diltiazem": {"category": "CCB", "dosage": "30-120mg", "interactions": ["Metoprolol", "Digoxin"]},
}

DIAGNOSIS_MEDICINE_MAP = {
    "hypertension": ["Amlodipine", "Enalapril", "Losartan", "Metoprolol"],
    "diabetes": ["Metformin"],
    "angina": ["Aspirin", "Amlodipine", "Metoprolol"],
    "heart failure": ["Furosemide", "Enalapril", "Digoxin"],
    "afib": ["Warfarin", "Metoprolol"],
    "high cholesterol": ["Atorvastatin", "Rosuvastatin"],
    "mi": ["Aspirin", "Clopidogrel", "Atorvastatin"],
    "chest pain": ["Aspirin"],
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_prescriptions (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                diagnosis TEXT, medicines TEXT NOT NULL,
                warnings TEXT DEFAULT '[]',
                notes TEXT DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def search_medicines(query: str) -> list[dict]:
    q = query.lower()
    results = []
    for name, info in MEDICINE_DB.items():
        if q in name.lower() or q in info["category"].lower():
            results.append({"name": name, **info})
    return results


def check_interaction(medicines: list[str]) -> list[dict]:
    warnings = []
    for i, m1 in enumerate(medicines):
        info1 = MEDICINE_DB.get(m1, {})
        for m2 in medicines[i+1:]:
            if m2 in info1.get("interactions", []):
                warnings.append({
                    "type": "drug_drug",
                    "severity": "moderate",
                    "message": f"⚠️ {m1} + {m2}: Potential interaction. Monitor closely."
                })
    return warnings


def suggest_medicines(diagnosis: str) -> list[str]:
    d = diagnosis.lower()
    suggested = set()
    for keyword, meds in DIAGNOSIS_MEDICINE_MAP.items():
        if keyword in d:
            for m in meds:
                suggested.add(m)
    return list(suggested)


def generate_prescription(patient_name: str, diagnosis: str,
                           medicines: list[str], notes: str = "",
                           patient_id: str = "") -> dict:
    warnings = check_interaction(medicines)
    suggested = suggest_medicines(diagnosis)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO ai_prescriptions (id, patient_id, patient_name, diagnosis, medicines, warnings, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (pid, patient_id, patient_name, diagnosis, json.dumps(medicines),
             json.dumps(warnings), notes, now)
        )
        conn.commit()
        return {"success": True, "id": pid, "warnings": warnings,
                "suggested": suggested,
                "message": f"✅ Prescription generated for {patient_name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_prescriptions(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ai_prescriptions ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
