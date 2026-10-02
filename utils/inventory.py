"""
Inventory / Pharmacy Module — Stock Management, Batch Tracking, Dispensing
===========================================================================
Manages hospital inventory with batch-wise and expiry-aware stock tracking.
Supports FEFO consumption (First Expiry First Out), stock movements,
low-stock alerts, and periodic stock audits.

Tables:
    inventory_categories — Hierarchical categories (medicine, consumable, surgical, etc.)
    inventory_items      — Master SKU records with reorder parameters
    inventory_batches    — Batch-level records with mfg/expiry dates and quantities
    stock_movements      — Immutable audit trail for every stock movement event
    stock_audits         — Audit session headers
    stock_audit_items    — Per-item counts during audit with variance tracking
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from utils.db import (
    USE_GOOGLE_SHEETS, USE_SUPABASE, USE_LOCAL_JSON, _gs_failed,
    call_gs_api, get_client, DB_FILE
)
import sqlite3

# ─── JSON fallback (lazy import) ──────────────────────────────────────────────
_json_module = None


def _get_json():
    global _json_module
    if _json_module is None and USE_LOCAL_JSON:
        from utils import local_json_db
        _json_module = local_json_db
    return _json_module


# ─── CONSTANTS ─────────────────────────────────────────────────────────────────

CATEGORY_TYPES = ["medicine", "consumable", "surgical", "lab_reagent", "other"]
UNITS = ["tab", "cap", "ml", "mg", "g", "l", "sheet", "pair", "bottle", "ampoule"]
MOVEMENT_TYPES = ["in", "out", "transfer", "adjustment"]
MOVEMENT_REFERENCES = ["purchase", "dispense", "return", "audit", "expiry"]
AUDIT_TYPES = ["full", "cyclical", "spot", "event"]

EXPIRY_ALERT_DAYS = [30, 60, 90]  # Lookahead windows


# ─── SCHEMA INIT ──────────────────────────────────────────────────────────────

def _init_inventory_tables():
    """Create inventory tables in SQLite if they don't exist."""
    if USE_SUPABASE or USE_GOOGLE_SHEETS:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category_type TEXT NOT NULL DEFAULT 'other',
                parent_id TEXT,
                requires_batch INTEGER NOT NULL DEFAULT 1,
                requires_expiry INTEGER NOT NULL DEFAULT 1,
                is_cold_chain INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id TEXT PRIMARY KEY,
                sku_code TEXT UNIQUE,
                name TEXT NOT NULL,
                generic_name TEXT DEFAULT '',
                category_id TEXT NOT NULL,
                manufacturer TEXT DEFAULT '',
                unit TEXT NOT NULL DEFAULT 'tab',
                reorder_level REAL NOT NULL DEFAULT 10,
                reorder_qty REAL NOT NULL DEFAULT 50,
                is_active INTEGER NOT NULL DEFAULT 1,
                hsn_code TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (category_id) REFERENCES inventory_categories(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_batches (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                batch_no TEXT NOT NULL,
                mfg_date TEXT,
                expiry_date TEXT,
                quantity REAL NOT NULL DEFAULT 0,
                unit_rate REAL NOT NULL DEFAULT 0,
                mrp REAL NOT NULL DEFAULT 0,
                supplier_id TEXT DEFAULT '',
                grn_ref TEXT DEFAULT '',
                is_cold_chain INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES inventory_items(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                reference_type TEXT DEFAULT '',
                reference_id TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES inventory_items(id),
                FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_audits (
                id TEXT PRIMARY KEY,
                audit_date TEXT NOT NULL,
                audit_type TEXT NOT NULL DEFAULT 'full',
                status TEXT NOT NULL DEFAULT 'in_progress',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_audit_items (
                id TEXT PRIMARY KEY,
                audit_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                expected_qty REAL NOT NULL DEFAULT 0,
                actual_qty REAL NOT NULL DEFAULT 0,
                variance REAL NOT NULL DEFAULT 0,
                resolved INTEGER NOT NULL DEFAULT 0,
                resolution_notes TEXT DEFAULT '',
                FOREIGN KEY (audit_id) REFERENCES stock_audits(id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES inventory_items(id),
                FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
            )
        """)
        conn.commit()

        # Seed default categories
        _seed_default_categories(cursor, conn)
    except Exception as e:
        print(f"[INVDB] init error: {e}")
    finally:
        conn.close()


def _seed_default_categories(cursor, conn):
    """Create default categories if none exist."""
    try:
        cursor.execute("SELECT COUNT(*) FROM inventory_categories")
        if cursor.fetchone()[0] > 0:
            return

        now_str = datetime.now().isoformat()
        defaults = [
            ("Cardiac Medications", "medicine", None),
            ("General Medications", "medicine", None),
            ("Consumables", "consumable", None),
            ("Surgical Supplies", "surgical", None),
            ("Lab Reagents", "lab_reagent", None),
            ("Other Supplies", "other", None),
        ]
        for name, ctype, parent in defaults:
            cid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO inventory_categories (id, name, category_type, parent_id, requires_batch, requires_expiry, created_at) "
                "VALUES (?, ?, ?, ?, 1, 1, ?)",
                (cid, name, ctype, parent, now_str)
            )
        conn.commit()
        print(f"[INVDB] Seeded {len(defaults)} inventory categories.")
    except Exception as e:
        print(f"[INVDB] seed categories error: {e}")


# Initialize on import
_init_inventory_tables()


# ═══════════════════════════════════════════════════════════════════════════════
#  CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_categories(category_type: str = "") -> list[dict]:
    """Get all inventory categories."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_categories_json(category_type)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM inventory_categories"
        params = []
        if category_type:
            query += " WHERE category_type=?"
            params.append(category_type)
        query += " ORDER BY name"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def create_category(name: str, category_type: str = "other",
                    requires_batch: bool = True, requires_expiry: bool = True,
                    is_cold_chain: bool = False) -> dict:
    """Create a new inventory category."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.create_inventory_category_json(name, category_type, requires_batch, requires_expiry, is_cold_chain)

    if category_type not in CATEGORY_TYPES:
        return {"success": False, "message": f"Invalid type. Choose from: {', '.join(CATEGORY_TYPES)}"}

    cid = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO inventory_categories (id, name, category_type, requires_batch, requires_expiry, is_cold_chain, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cid, name, category_type, int(requires_batch), int(requires_expiry), int(is_cold_chain), now_str)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Category '{name}' created.", "id": cid}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create category: {e}"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ITEMS (SKUs)
# ═══════════════════════════════════════════════════════════════════════════════

def create_item(name: str, category_id: str, unit: str = "tab",
                generic_name: str = "", manufacturer: str = "",
                reorder_level: float = 10.0, reorder_qty: float = 50.0,
                sku_code: str = "", hsn_code: str = "") -> dict:
    """Create a new inventory item (SKU)."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.create_inventory_item_json(
            name, category_id, unit, generic_name, manufacturer,
            reorder_level, reorder_qty, sku_code, hsn_code
        )

    if unit not in UNITS:
        return {"success": False, "message": f"Invalid unit. Choose from: {', '.join(UNITS)}"}

    item_id = str(uuid.uuid4())
    code = sku_code or f"SKU-{item_id[:8].upper()}"
    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO inventory_items (id, sku_code, name, generic_name, category_id, "
            "manufacturer, unit, reorder_level, reorder_qty, is_active, hsn_code, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (item_id, code, name, generic_name, category_id,
             manufacturer, unit, reorder_level, reorder_qty, hsn_code, now_str)
        )
        conn.commit()
        return {"success": True, "message": f"✅ '{name}' added to inventory.", "id": item_id, "sku": code}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create item: {e}"}
    finally:
        conn.close()


def get_items(category_id: str = "", search: str = "",
              active_only: bool = True) -> list[dict]:
    """Get inventory items, optionally filtered."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_items_json(category_id, search, active_only)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT i.*, c.name AS category_name, c.category_type
            FROM inventory_items i
            LEFT JOIN inventory_categories c ON i.category_id = c.id
            WHERE 1=1
        """
        params = []
        if active_only:
            query += " AND i.is_active=1"
        if category_id:
            query += " AND i.category_id=?"
            params.append(category_id)
        if search:
            query += " AND (i.name LIKE ? OR i.generic_name LIKE ? OR i.sku_code LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        query += " ORDER BY i.name"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_item(item_id: str) -> dict | None:
    """Get a single item by ID."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_item_json(item_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT i.*, c.name AS category_name, c.category_type
            FROM inventory_items i
            LEFT JOIN inventory_categories c ON i.category_id = c.id
            WHERE i.id=?
        """, (item_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    except Exception:
        return None
    finally:
        conn.close()


def update_item(item_id: str, **kwargs) -> dict:
    """Update fields of an inventory item."""
    allowed = {"name", "generic_name", "manufacturer", "unit",
               "reorder_level", "reorder_qty", "is_active", "hsn_code"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return {"success": False, "message": "No valid fields to update."}

    json_mod = _get_json()
    if json_mod:
        return json_mod.update_inventory_item_json(item_id, updates)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [item_id]
        cursor.execute(f"UPDATE inventory_items SET {set_clause} WHERE id=?", values)
        conn.commit()
        return {"success": True, "message": "✅ Item updated."}
    except Exception as e:
        return {"success": False, "message": f"❌ Update failed: {e}"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  BATCHES
# ═══════════════════════════════════════════════════════════════════════════════

def add_batch(item_id: str, batch_no: str, quantity: float, unit_rate: float,
              mrp: float = 0.0, mfg_date: str = "", expiry_date: str = "",
              supplier_id: str = "", grn_ref: str = "",
              is_cold_chain: bool = False, created_by: str = "") -> dict:
    """Add stock to inventory as a new batch (purchase receipt)."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.add_inventory_batch_json(
            item_id, batch_no, quantity, unit_rate, mrp,
            mfg_date, expiry_date, supplier_id, grn_ref,
            is_cold_chain, created_by
        )

    batch_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO inventory_batches (id, item_id, batch_no, mfg_date, expiry_date, "
            "quantity, unit_rate, mrp, supplier_id, grn_ref, is_cold_chain, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (batch_id, item_id, batch_no, mfg_date, expiry_date,
             quantity, unit_rate, mrp, supplier_id, grn_ref,
             int(is_cold_chain), now_str)
        )
        # Record movement
        cursor.execute(
            "INSERT INTO stock_movements (id, item_id, batch_id, movement_type, quantity, "
            "reference_type, reference_id, notes, created_by, created_at) "
            "VALUES (?, ?, ?, 'in', ?, 'purchase', ?, ?, ?, ?)",
            (str(uuid.uuid4()), item_id, batch_id, quantity, grn_ref,
             f"GRN: {grn_ref or 'Direct'}", created_by, now_str)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Batch {batch_no} added ({quantity} units).", "batch_id": batch_id}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to add batch: {e}"}
    finally:
        conn.close()


def get_batches(item_id: str = "", low_stock_only: bool = False,
                expiring_within_days: int = 0) -> list[dict]:
    """Get batches, optionally filtered by item, low stock, or expiry."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_batches_json(item_id, low_stock_only, expiring_within_days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT b.*, i.name AS item_name, i.sku_code, i.unit, i.reorder_level
            FROM inventory_batches b
            JOIN inventory_items i ON b.item_id = i.id
            WHERE 1=1
        """
        params = []
        if item_id:
            query += " AND b.item_id=?"
            params.append(item_id)
        if low_stock_only:
            query += " AND b.quantity <= i.reorder_level"
        if expiring_within_days > 0:
            cutoff = (date.today() + timedelta(days=expiring_within_days)).isoformat()
            query += " AND b.expiry_date <= ? AND b.expiry_date >= ?"
            params.extend([cutoff, date.today().isoformat()])
        query += " ORDER BY b.expiry_date ASC, b.batch_no"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_batch(batch_id: str) -> dict | None:
    """Get a single batch by ID."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_batch_json(batch_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT b.*, i.name AS item_name, i.sku_code, i.unit
            FROM inventory_batches b
            JOIN inventory_items i ON b.item_id = i.id
            WHERE b.id=?
        """, (batch_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    except Exception:
        return None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  DISPENSING (FEFO)
# ═══════════════════════════════════════════════════════════════════════════════

def get_total_stock(item_id: str) -> float:
    """Get total available stock for an item across all batches."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_total_stock_json(item_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM inventory_batches WHERE item_id=?",
            (item_id,)
        )
        return cursor.fetchone()[0]
    except Exception:
        return 0.0
    finally:
        conn.close()


def dispense_item(item_id: str, quantity: float, reference_type: str = "dispense",
                  reference_id: str = "", created_by: str = "",
                  notes: str = "") -> dict:
    """
    Dispense stock using FEFO (First Expiry First Out).
    Deducts from the soonest-expiring batch first.
    Returns: {"success": bool, "message": str, "dispensed": list[dict]}
    """
    json_mod = _get_json()
    if json_mod:
        return json_mod.dispense_inventory_item_json(
            item_id, quantity, reference_type, reference_id, created_by, notes
        )

    if quantity <= 0:
        return {"success": False, "message": "❌ Quantity must be positive."}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Get batches with stock, sorted by expiry (FEFO)
        cursor.execute("""
            SELECT id, quantity, batch_no, expiry_date
            FROM inventory_batches
            WHERE item_id=? AND quantity > 0
            ORDER BY expiry_date ASC, created_at ASC
        """, (item_id,))
        batches = cursor.fetchall()

        if not batches:
            return {"success": False, "message": "❌ No stock available for this item."}

        total_available = sum(b[1] for b in batches)
        if quantity > total_available:
            return {
                "success": False,
                "message": f"❌ Insufficient stock. Available: {total_available}, Requested: {quantity}"
            }

        remaining = quantity
        dispensed_batches = []
        now_str = datetime.now().isoformat()

        for batch_id, batch_qty, batch_no, expiry in batches:
            if remaining <= 0:
                break
            deduct = min(remaining, batch_qty)
            cursor.execute(
                "UPDATE inventory_batches SET quantity = quantity - ? WHERE id=?",
                (deduct, batch_id)
            )
            # Record movement
            cursor.execute(
                "INSERT INTO stock_movements (id, item_id, batch_id, movement_type, quantity, "
                "reference_type, reference_id, notes, created_by, created_at) "
                "VALUES (?, ?, ?, 'out', ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), item_id, batch_id, deduct,
                 reference_type, reference_id, notes, created_by, now_str)
            )
            dispensed_batches.append({
                "batch_id": batch_id,
                "batch_no": batch_no,
                "quantity": deduct,
                "expiry_date": expiry,
            })
            remaining -= deduct

        conn.commit()
        return {
            "success": True,
            "message": f"✅ Dispensed {quantity} units from {len(dispensed_batches)} batch(es).",
            "dispensed": dispensed_batches
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Dispense failed: {e}"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  STOCK MOVEMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def get_movements(item_id: str = "", movement_type: str = "",
                  days: int = 30) -> list[dict]:
    """Get stock movement log, optionally filtered."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_stock_movements_json(item_id, movement_type, days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = """
            SELECT m.*, i.name AS item_name, i.sku_code, i.unit, b.batch_no
            FROM stock_movements m
            JOIN inventory_items i ON m.item_id = i.id
            LEFT JOIN inventory_batches b ON m.batch_id = b.id
            WHERE m.created_at >= ?
        """
        params = [cutoff]
        if item_id:
            query += " AND m.item_id=?"
            params.append(item_id)
        if movement_type:
            query += " AND m.movement_type=?"
            params.append(movement_type)
        query += " ORDER BY m.created_at DESC LIMIT 200"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  LOW STOCK & EXPIRY ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def get_low_stock_items() -> list[dict]:
    """Get items where total stock is below reorder level."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_low_stock_items_json()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT i.id, i.name, i.sku_code, i.unit, i.reorder_level, i.reorder_qty,
                   COALESCE(SUM(b.quantity), 0) AS total_stock,
                   c.name AS category_name
            FROM inventory_items i
            LEFT JOIN inventory_batches b ON b.item_id = i.id
            LEFT JOIN inventory_categories c ON i.category_id = c.id
            WHERE i.is_active=1
            GROUP BY i.id
            HAVING total_stock <= i.reorder_level
            ORDER BY total_stock ASC
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_expiring_batches(days: int = 30) -> list[dict]:
    """Get batches expiring within X days."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_expiring_batches_json(days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today = date.today().isoformat()
        cursor.execute("""
            SELECT b.*, i.name AS item_name, i.sku_code, i.unit
            FROM inventory_batches b
            JOIN inventory_items i ON b.item_id = i.id
            WHERE b.expiry_date IS NOT NULL
              AND b.expiry_date <= ? AND b.expiry_date >= ?
              AND b.quantity > 0
            ORDER BY b.expiry_date ASC
        """, (cutoff, today))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  STOCK AUDITS
# ═══════════════════════════════════════════════════════════════════════════════

def create_audit(audit_type: str = "full", notes: str = "",
                 created_by: str = "") -> dict:
    """Create a new stock audit session."""
    if audit_type not in AUDIT_TYPES:
        return {"success": False, "message": f"Invalid type. Choose from: {', '.join(AUDIT_TYPES)}"}

    json_mod = _get_json()
    if json_mod:
        return json_mod.create_stock_audit_json(audit_type, notes, created_by)

    audit_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    today_str = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO stock_audits (id, audit_date, audit_type, status, notes, created_by, created_at) "
            "VALUES (?, ?, ?, 'in_progress', ?, ?, ?)",
            (audit_id, today_str, audit_type, notes, created_by, now_str)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Audit '{audit_type}' created.", "audit_id": audit_id}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create audit: {e}"}
    finally:
        conn.close()


def record_audit_item(audit_id: str, item_id: str, batch_id: str,
                      expected_qty: float, actual_qty: float,
                      resolution_notes: str = "") -> dict:
    """Record actual count for one item during audit."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.record_audit_item_json(audit_id, item_id, batch_id, expected_qty, actual_qty, resolution_notes)

    variance = actual_qty - expected_qty
    resolved = 1 if abs(variance) < 0.01 else 0
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO stock_audit_items (id, audit_id, item_id, batch_id, expected_qty, "
            "actual_qty, variance, resolved, resolution_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), audit_id, item_id, batch_id, expected_qty,
             actual_qty, variance, resolved, resolution_notes)
        )
        conn.commit()
        return {"success": True, "message": "✅ Audit entry recorded."}
    except Exception as e:
        return {"success": False, "message": f"❌ Audit recording failed: {e}"}
    finally:
        conn.close()


def complete_audit(audit_id: str) -> dict:
    """Mark audit as completed."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.complete_stock_audit_json(audit_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE stock_audits SET status='completed' WHERE id=?", (audit_id,))
        conn.commit()
        return {"success": True, "message": "✅ Audit completed."}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to close audit: {e}"}
    finally:
        conn.close()


def get_audits(limit: int = 20) -> list[dict]:
    """Get recent stock audits."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_stock_audits_json(limit)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM stock_audits ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_audit_items(audit_id: str) -> list[dict]:
    """Get all items in an audit."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_audit_items_json(audit_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ai.*, i.name AS item_name, i.sku_code, b.batch_no
            FROM stock_audit_items ai
            JOIN inventory_items i ON ai.item_id = i.id
            LEFT JOIN inventory_batches b ON ai.batch_id = b.id
            WHERE ai.audit_id=?
        """, (audit_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def get_inventory_summary() -> dict:
    """Get summary stats for the inventory dashboard."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_inventory_summary_json()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        total_items = cursor.execute(
            "SELECT COUNT(*) FROM inventory_items WHERE is_active=1"
        ).fetchone()[0]

        total_batches = cursor.execute(
            "SELECT COUNT(*) FROM inventory_batches"
        ).fetchone()[0]

        total_stock_value = cursor.execute(
            "SELECT COALESCE(SUM(b.quantity * b.unit_rate), 0) FROM inventory_batches b"
        ).fetchone()[0]

        low_stock_count = cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT i.id, COALESCE(SUM(b.quantity), 0) AS total
                FROM inventory_items i
                LEFT JOIN inventory_batches b ON b.item_id = i.id
                WHERE i.is_active=1
                GROUP BY i.id
                HAVING total <= i.reorder_level
            )
        """).fetchone()[0]

        expiring_30 = cursor.execute("""
            SELECT COUNT(*) FROM inventory_batches
            WHERE expiry_date IS NOT NULL
              AND expiry_date <= ? AND expiry_date >= ?
              AND quantity > 0
        """, ((date.today() + timedelta(days=30)).isoformat(), date.today().isoformat())).fetchone()[0]

        return {
            "total_items": total_items,
            "total_batches": total_batches,
            "total_stock_value": total_stock_value,
            "low_stock_count": low_stock_count,
            "expiring_30_days": expiring_30,
        }
    except Exception:
        return {
            "total_items": 0, "total_batches": 0, "total_stock_value": 0,
            "low_stock_count": 0, "expiring_30_days": 0,
        }
    finally:
        conn.close()
