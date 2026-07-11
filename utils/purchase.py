"""
Purchase / Procurement Module — Purchase Orders, GRN Tracking
===============================================================
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3

PO_STATUSES = ["draft", "approved", "ordered", "partial", "received", "cancelled"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id TEXT PRIMARY KEY, po_number TEXT UNIQUE,
                supplier_name TEXT NOT NULL, supplier_id TEXT DEFAULT '',
                order_date TEXT NOT NULL, expected_date TEXT,
                status TEXT DEFAULT 'draft', total_amount REAL DEFAULT 0,
                notes TEXT DEFAULT '', created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id TEXT PRIMARY KEY, po_id TEXT NOT NULL,
                item_name TEXT NOT NULL, sku_code TEXT DEFAULT '',
                quantity REAL NOT NULL, unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0, received_qty REAL DEFAULT 0,
                FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def create_po(supplier_name: str, supplier_id: str = "", notes: str = "",
              expected_date: str = "", created_by: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        po_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        po_num = f"PO-{datetime.now().strftime('%y%m%d-%H%M%S')}"
        cursor.execute(
            "INSERT INTO purchase_orders (id, po_number, supplier_name, supplier_id, order_date, "
            "expected_date, status, notes, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (po_id, po_num, supplier_name, supplier_id, date.today().isoformat(),
             expected_date or None, "draft", notes, created_by, now, now)
        )
        conn.commit()
        return {"success": True, "message": f"📋 PO {po_num} created.", "po_id": po_id, "po_number": po_num}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def add_po_item(po_id: str, item_name: str, quantity: float, unit_price: float,
                sku_code: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        iid = str(uuid.uuid4())
        total = quantity * unit_price
        cursor.execute(
            "INSERT INTO purchase_order_items (id, po_id, item_name, sku_code, quantity, unit_price, total_price) "
            "VALUES (?,?,?,?,?,?,?)",
            (iid, po_id, item_name, sku_code, quantity, unit_price, total)
        )
        # Update PO total
        cursor.execute("UPDATE purchase_orders SET total_amount = (SELECT COALESCE(SUM(total_price),0) FROM purchase_order_items WHERE po_id=?) WHERE id=?",
                       (po_id, po_id))
        conn.commit()
        return {"success": True, "message": f"✅ {item_name} added."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def update_po_status(po_id: str, status: str) -> dict:
    if status not in PO_STATUSES:
        return {"success": False, "message": "Invalid status."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute("UPDATE purchase_orders SET status=?, updated_at=? WHERE id=?", (status, now, po_id))
        conn.commit()
        return {"success": True, "message": f"✅ PO {status}."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_pos(status: str = "") -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM purchase_orders"
        params = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT 50"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_po_items(po_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM purchase_order_items WHERE po_id=?", (po_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
