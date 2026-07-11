"""
AI Receptionist — Smart Patient Greeting, Department Routing, FAQ
====================================================================
"""
import uuid
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

FAQ = {
    "timing": "Our clinic is open Monday-Saturday, 9:00 AM to 6:00 PM.",
    "appointment": "You can book an appointment online or call reception.",
    "report": "Reports are ready within 1-2 hours after test completion.",
    "payment": "We accept cash, card, UPI, and insurance.",
    "ecg": "ECG takes about 10-15 minutes. No special preparation needed.",
    "echo": "Echocardiogram takes 20-30 minutes. Wear comfortable clothes.",
    "tmt": "TMT (Stress Test) takes 30-45 minutes. Avoid heavy meals before.",
    "holter": "Holter monitoring is 24-hour recording. You can go home with it.",
    "abpm": "ABPM is 24-hour BP monitoring. Normal activities allowed.",
    "ipd": "IPD admission requires doctor recommendation. Visit reception for admission.",
    "insurance": "We accept all major health insurance providers. Bring your card.",
    "cancellation": "Please cancel at least 2 hours before your appointment.",
    "doctor": "Dr. Sharma is available Mon-Sat, 10:00 AM to 4:00 PM.",
    "parking": "Free parking available for patients and visitors.",
    "emergency": "For emergencies, call 108 or visit our emergency department directly.",
}

GREETINGS = ["hi", "hello", "hey", "good morning", "good evening", "namaste", "नमस्ते"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_reception_log (
                id TEXT PRIMARY KEY, patient_name TEXT, mobile TEXT,
                query TEXT NOT NULL, response TEXT NOT NULL,
                intent TEXT DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def process_query(patient_name: str, mobile: str, query: str) -> dict:
    """Process natural language query and return response."""
    q = query.lower().strip()
    
    # Greeting
    if any(g in q for g in GREETINGS):
        response = f"👋 Namaste {patient_name or 'ji'}! Welcome to CardioQueue. How can I assist you today?"
        intent = "greeting"
    # Appointment
    elif any(kw in q for kw in ["appointment", "book", "schedule"]):
        response = "📅 You can book an appointment at reception or use the Appointments page. Available slots: Mon-Sat, 9 AM-5 PM."
        intent = "appointment"
    # Report
    elif any(kw in q for kw in ["report", "result", "status"]):
        response = "📋 Check your report status on the Patient Status page using your mobile number. Reports are typically ready in 1-2 hours."
        intent = "report"
    # Timing
    elif any(kw in q for kw in ["timing", "time", "open", "closed", "hour"]):
        response = FAQ["timing"]
        intent = "timing"
    # Emergency
    elif any(kw in q for kw in ["emergency", "urgent", "ambulance", "108"]):
        response = "🚑 **EMERGENCY** — Please call 108 immediately or rush to our Emergency Department. Do not wait."
        intent = "emergency"
    # Payment
    elif any(kw in q for kw in ["payment", "pay", "cost", "price", "fee", "bill"]):
        response = FAQ["payment"]
        intent = "payment"
    # Insurance
    elif any(kw in q for kw in ["insurance", "claim", "cover"]):
        response = FAQ["insurance"]
        intent = "insurance"
    # Doctor
    elif any(kw in q for kw in ["doctor", "dr.", "specialist", "consult"]):
        response = FAQ["doctor"]
        intent = "doctor"
    # IPD
    elif any(kw in q for kw in ["admit", "ipd", "ward", "bed", "hospitalize"]):
        response = FAQ["ipd"]
        intent = "ipd"
    # Test info
    elif any(kw in q for kw in ["ecg", "echo", "tmt", "test", "investigation"]):
        if "ecg" in q:
            response = FAQ["ecg"]
        elif "echo" in q:
            response = FAQ["echo"]
        elif "tmt" in q:
            response = FAQ["tmt"]
        else:
            response = "We offer ECG, Echo, TMT, Holter, ABPM, OPD, X-Ray, and Ultrasound. Which one would you like to know about?"
        intent = "test_info"
    else:
        response = "I couldn't understand your query. Please visit reception or call us for assistance."
        intent = "unknown"

    # Log
    log_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "INSERT INTO ai_reception_log (id, patient_name, mobile, query, response, intent, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, patient_name, mobile, query, response, intent, now)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    return {"response": response, "intent": intent, "id": log_id}


def get_reception_log(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ai_reception_log ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
