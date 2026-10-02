import uuid,json
from datetime import datetime,timedelta
from utils.db import DB_FILE
import sqlite3,os
def _init_tables():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS system_metrics (id TEXT PRIMARY KEY,metric_name TEXT NOT NULL,metric_value REAL,unit TEXT DEFAULT '',created_at TEXT NOT NULL)")
    conn.commit(); conn.close()
_init_tables()
def record_metric(name,value,unit=''):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("INSERT INTO system_metrics(id,metric_name,metric_value,unit,created_at) VALUES(?,?,?,?,?)",
        (str(uuid.uuid4()),name,value,unit,datetime.now().isoformat()))
    conn.commit(); conn.close()
def get_db_size():
    try: return round(os.path.getsize(DB_FILE)/1024,1)
    except: return 0
def get_page_count():
    return len([f for f in os.listdir('pages') if f.endswith('.py') and not f.startswith('_')])
def get_util_count():
    return len([f for f in os.listdir('utils') if f.endswith('.py') and not f.startswith('_')])
