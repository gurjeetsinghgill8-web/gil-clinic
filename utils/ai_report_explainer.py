"""
AI Report Explainer — Converts Medical Reports to Patient-Friendly Language
=============================================================================
Rule-based explanation engine for common lab tests and diagnostic reports.
"""
import uuid
import json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

# Normal reference ranges
REFERENCE_RANGES = {
    "Hemoglobin": {"unit": "g/dL", "male": [13, 17], "female": [12, 15.5], "child": [11, 16]},
    "WBC": {"unit": "10³/µL", "range": [4.0, 11.0]},
    "RBC": {"unit": "10⁶/µL", "male": [4.7, 6.1], "female": [4.2, 5.4]},
    "Platelets": {"unit": "10³/µL", "range": [150, 450]},
    "Blood Sugar (Fasting)": {"unit": "mg/dL", "range": [70, 110]},
    "Blood Sugar (PP)": {"unit": "mg/dL", "range": [70, 140]},
    "HbA1c": {"unit": "%", "range": [4.0, 5.7]},
    "Total Cholesterol": {"unit": "mg/dL", "range": [125, 200]},
    "HDL": {"unit": "mg/dL", "range": [40, 60]},
    "LDL": {"unit": "mg/dL", "range": [0, 130]},
    "Triglycerides": {"unit": "mg/dL", "range": [0, 150]},
    "Creatinine": {"unit": "mg/dL", "range": [0.6, 1.2]},
    "BUN": {"unit": "mg/dL", "range": [7, 20]},
    "SGPT (ALT)": {"unit": "U/L", "range": [7, 56]},
    "SGOT (AST)": {"unit": "U/L", "range": [10, 40]},
    "TSH": {"unit": "µIU/mL", "range": [0.4, 4.0]},
    "T3": {"unit": "ng/dL", "range": [80, 200]},
    "T4": {"unit": "µg/dL", "range": [5.0, 12.0]},
    "Potassium": {"unit": "mEq/L", "range": [3.5, 5.0]},
    "Sodium": {"unit": "mEq/L", "range": [136, 145]},
}

SIMPLE_EXPLANATIONS = {
    "Hemoglobin": "Measures oxygen-carrying capacity of blood. Low = anemia (fatigue, weakness). High = dehydration or lung issues.",
    "WBC": "White blood cells fight infection. High = infection/inflammation. Low = immune suppression.",
    "Platelets": "Helps blood clot. Low = bleeding risk. High = clotting risk.",
    "Blood Sugar (Fasting)": "Measures blood glucose after 8hr fasting. High = diabetes risk.",
    "HbA1c": "Average blood sugar over 3 months. >6.5% = diabetes. 5.7-6.4% = prediabetes.",
    "Total Cholesterol": "High = increased heart disease risk. Lower through diet and exercise.",
    "Creatinine": "Kidney function marker. High = reduced kidney function. Low = usually normal.",
    "SGPT (ALT)": "Liver enzyme. High = liver stress/inflammation (hepatitis, fatty liver).",
    "TSH": "Thyroid function. High = hypothyroidism (slow metabolism). Low = hyperthyroidism (overactive).",
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_report_explanations (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                report_type TEXT, original_text TEXT,
                explanation TEXT NOT NULL, language TEXT DEFAULT 'en',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def _get_range(test_name: str, gender: str = "male") -> list:
    """Get reference range for a test, considering gender."""
    ref = REFERENCE_RANGES.get(test_name, {})
    if "range" in ref:
        return ref["range"]
    gender_key = "male" if gender.lower() in ("male", "m") else "female"
    if gender_key in ref:
        return ref[gender_key]
    return [0, 100]


def explain_test_value(test_name: str, value: float, unit: str = "",
                       gender: str = "male") -> dict:
    """Generate patient-friendly explanation for a single test value."""
    ref_range = _get_range(test_name, gender)
    ref = REFERENCE_RANGES.get(test_name, {})
    unit = unit or ref.get("unit", "")
    low, high = ref_range

    if value < low:
        status = "low"
        icon = "🔻"
        flag = "Below normal"
    elif value > high:
        status = "high"
        icon = "🔺"
        flag = "Above normal"
    else:
        status = "normal"
        icon = "✅"
        flag = "Normal range"

    simple = SIMPLE_EXPLANATIONS.get(test_name, "Consult your doctor for interpretation.")
    explanation = f"{icon} **{test_name}**: {value} {unit} — {flag} ({low}-{high} {unit})"
    return {
        "test": test_name,
        "value": value,
        "unit": unit,
        "range": f"{low}-{high}",
        "status": status,
        "icon": icon,
        "flag": flag,
        "simple_explanation": simple,
        "explanation": explanation,
    }


def explain_report(patient_name: str, report_type: str,
                   test_values: list[dict], patient_id: str = "",
                   gender: str = "male") -> dict:
    """Generate full report explanation."""
    explanations = []
    flagged = []
    for tv in test_values:
        result = explain_test_value(
            tv.get("name", "Unknown"),
            tv.get("value", 0),
            tv.get("unit", ""),
            gender
        )
        explanations.append(result)
        if result["status"] != "normal":
            flagged.append(result)

    report = {
        "patient_name": patient_name,
        "report_type": report_type,
        "generated_at": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
        "test_count": len(explanations),
        "normal_count": sum(1 for e in explanations if e["status"] == "normal"),
        "abnormal_count": len(flagged),
        "results": explanations,
        "flagged": flagged,
        "summary": f"Found {len(flagged)} abnormal {'result' if len(flagged)==1 else 'results'} out of {len(explanations)} tests." if flagged else "All tests are within normal range. ✅",
    }

    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ai_report_explanations (id, patient_id, patient_name, report_type, original_text, explanation, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), patient_id, patient_name, report_type,
             json.dumps(test_values), json.dumps(report), datetime.now().isoformat())
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    return {"success": True, "report": report}
