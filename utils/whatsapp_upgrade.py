"""
WhatsApp Cloud API — Meta Business Integration
"""
import uuid, json, requests
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

WHATSAPP_API_URL = "https://graph.facebook.com/v18.0/"
PHONE_NUMBER_ID = ""
ACCESS_TOKEN = ""

def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS whatsapp_templates (id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,category TEXT,language TEXT DEFAULT 'en',body TEXT NOT NULL,status TEXT DEFAULT 'pending',template_id TEXT,created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS whatsapp_messages (id TEXT PRIMARY KEY,recipient TEXT NOT NULL,template_name TEXT,message TEXT,status TEXT DEFAULT 'pending',wa_message_id TEXT,conversation_id TEXT,created_at TEXT NOT NULL)")
    conn.commit()
    conn.close()

_init_tables()

def send_template(to_number, template_name, params=None):
    if not ACCESS_TOKEN:
        return {"success": False, "message": "WhatsApp not configured. Set ACCESS_TOKEN and PHONE_NUMBER_ID in utils/whatsapp_upgrade.py"}
    url = f"{WHATSAPP_API_URL}{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    body = {"messaging_product": "whatsapp", "to": to_number, "type": "template", "template": {"name": template_name, "language": {"code": "en"}}}
    if params:
        body["template"]["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    try:
        r = requests.post(url, json=body, headers=headers, timeout=10)
        data = r.json()
        if r.status_code == 200:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO whatsapp_messages(id,recipient,template_name,status,wa_message_id,created_at) VALUES(?,?,?,?,?,?)",
                      (str(uuid.uuid4()), to_number, template_name, "sent", data.get("messages", [{}])[0].get("id", ""), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return {"success": True, "wa_id": data.get("messages", [{}])[0].get("id", "")}
        return {"success": False, "message": str(data)}
    except Exception as e:
        return {"success": False, "message": str(e)}

def send_text(to_number, text):
    if not ACCESS_TOKEN:
        return {"success": False, "message": "WhatsApp not configured."}
    url = f"{WHATSAPP_API_URL}{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    body = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text}}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=10)
        if r.status_code == 200:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO whatsapp_messages(id,recipient,message,status,created_at) VALUES(?,?,?,?,?)",
                      (str(uuid.uuid4()), to_number, text, "sent", datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return {"success": True}
        return {"success": False, "message": str(r.json())}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_whatsapp_log(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM whatsapp_messages ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

def get_templates():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM whatsapp_templates ORDER BY created_at DESC")
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]