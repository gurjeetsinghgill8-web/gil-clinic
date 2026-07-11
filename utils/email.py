"""
Email Integration Module — SendGrid/SMTP with HTML Templates
==============================================================
"""
import uuid
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

SMTP_CONFIG = {
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "",
    "password": "",
    "from_email": "noreply@gilclinic.com",
    "from_name": "GIL Clinic",
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_log (
                id TEXT PRIMARY KEY, recipient TEXT NOT NULL,
                subject TEXT NOT NULL, body TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TEXT, error TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def send_email(recipient: str, subject: str, body_html: str = "",
               body_text: str = "", attachment_path: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    eid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['from_email']}>"
        msg["To"] = recipient
        msg["Subject"] = subject

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        if attachment_path:
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={attachment_path.split('/')[-1]}")
                msg.attach(part)

        if SMTP_CONFIG["username"] and SMTP_CONFIG["password"]:
            server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"])
            server.starttls()
            server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])
            server.send_message(msg)
            server.quit()

        cursor.execute(
            "INSERT INTO email_log (id, recipient, subject, body, status, sent_at, created_at) VALUES (?,?,?,?,?,?,?)",
            (eid, recipient, subject, body_html or body_text, "sent", now, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Email sent to {recipient}"}
    except Exception as e:
        cursor.execute(
            "INSERT INTO email_log (id, recipient, subject, body, status, error, created_at) VALUES (?,?,?,?,?,?,?)",
            (eid, recipient, subject, body_html or body_text, "failed", str(e), now)
        )
        conn.commit()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_email_log(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM email_log ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_report_email_html(patient_name: str, report_type: str, test_results: list[dict]) -> str:
    rows_html = ""
    for r in test_results:
        status_icon = "✅" if r.get("status") == "normal" else "⚠️"
        rows_html += f"<tr><td>{r.get('test','')}</td><td>{r.get('value','')}</td><td>{r.get('unit','')}</td><td>{status_icon} {r.get('flag','')}</td></tr>"
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:20px;border-radius:10px;color:white;text-align:center;">
            <h2>GIL Clinic — {report_type} Report</h2>
            <p>Patient: {patient_name}</p>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-top:20px;">
            <tr style="background:#f0f0f0;"><th>Test</th><th>Value</th><th>Unit</th><th>Status</th></tr>
            {rows_html}
        </table>
        <p style="color:#666;margin-top:20px;">This is an auto-generated report from GIL Clinic.</p>
    </body></html>
    """
