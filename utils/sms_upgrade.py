import uuid, json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3
def _init_tables():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS sms_templates (id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,template_id TEXT,body TEXT NOT NULL,language TEXT DEFAULT 'en',dlt_template_id TEXT DEFAULT '',status TEXT DEFAULT 'pending',created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS sms_log_v2 (id TEXT PRIMARY KEY,recipient TEXT NOT NULL,provider TEXT,template_name TEXT,message TEXT,status TEXT DEFAULT 'pending',delivery_status TEXT DEFAULT '',dlr_data TEXT DEFAULT '{}',cost REAL DEFAULT 0.0,created_at TEXT NOT NULL)")
    conn.commit(); conn.close()
_init_tables()
def create_template(name,body,lang='en',dlt_id=''):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    try:
        c.execute("INSERT INTO sms_templates(id,name,template_id,body,language,dlt_template_id,created_at) VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()),name,name.lower().replace(' ','_'),body,lang,dlt_id,datetime.now().isoformat()))
        conn.commit(); return {'success':True,'message':f'Template {name} created'}
    except Exception as e: return {'success':False,'message':str(e)}
    finally: conn.close()
def get_templates():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    try:
        c.execute("SELECT * FROM sms_templates ORDER BY created_at DESC")
        rows=c.fetchall(); cols=[d[0] for d in c.description]
        return [dict(zip(cols,r)) for r in rows]
    except: return []
    finally: conn.close()
def send_sms_v2(recipient,msg,template='',provider='twilio'):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    log_id=str(uuid.uuid4()); now=datetime.now().isoformat()
    try:
        from utils.sms import send_sms
        r=send_sms(recipient,msg)
        c.execute("INSERT INTO sms_log_v2(id,recipient,provider,template_name,message,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (log_id,recipient,provider,template,msg,'sent' if r.get('success') else 'failed',now))
        conn.commit(); return r
    except Exception as e:
        c.execute("INSERT INTO sms_log_v2(id,recipient,provider,template_name,message,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (log_id,recipient,provider,template,msg,'failed',now))
        conn.commit(); return {'success':False,'message':str(e)}
    finally: conn.close()
def get_sms_log_v2(limit=100):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    try:
        c.execute("SELECT * FROM sms_log_v2 ORDER BY created_at DESC LIMIT ?",(limit,))
        rows=c.fetchall(); cols=[d[0] for d in c.description]
        return [dict(zip(cols,r)) for r in rows]
    except: return []
    finally: conn.close()
