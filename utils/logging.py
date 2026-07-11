import uuid,json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3
def _init_tables():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS app_logs (id TEXT PRIMARY KEY,level TEXT NOT NULL DEFAULT 'info',module TEXT,message TEXT NOT NULL,details TEXT DEFAULT '{}',created_at TEXT NOT NULL)")
    conn.commit(); conn.close()
_init_tables()
def log(level,module,message,details=None):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("INSERT INTO app_logs(id,level,module,message,details,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid.uuid4()),level,module,message,json.dumps(details or {}),datetime.now().isoformat()))
    conn.commit(); conn.close()
def get_logs(level='',limit=100):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    q="SELECT * FROM app_logs"
    p=[]
    if level: q+=" WHERE level=?"; p.append(level)
    q+=" ORDER BY created_at DESC LIMIT ?"; p.append(limit)
    c.execute(q,p)
    rows=c.fetchall(); cols=[d[0] for d in c.description]
    conn.close()
    return [dict(zip(cols,r)) for r in rows]
