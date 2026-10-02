import uuid
from datetime import datetime
from utils.db import DB_FILE
import sqlite3
def _init_tables():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS branches (id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,code TEXT UNIQUE,address TEXT,phone TEXT,email TEXT,is_active INTEGER DEFAULT 1,created_at TEXT NOT NULL)")
    conn.commit(); conn.close()
_init_tables()
def add_branch(name,code,address='',phone='',email=''):
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("INSERT INTO branches(id,name,code,address,phone,email,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(uuid.uuid4()),name,code,address,phone,email,datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {'success':True,'message':f'Branch {name} added'}
def get_branches():
    conn=sqlite3.connect(DB_FILE); c=conn.cursor()
    c.execute("SELECT * FROM branches WHERE is_active=1 ORDER BY name")
    rows=c.fetchall(); cols=[d[0] for d in c.description]
    conn.close()
    return [dict(zip(cols,r)) for r in rows]
