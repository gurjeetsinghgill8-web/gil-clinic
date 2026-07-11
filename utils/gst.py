"""
GST Compliance Module — Tax Calculation, HSN/SAC Mapping, Invoice Format
===========================================================================
"""
import json
import uuid
from datetime import datetime, date
from utils.db import DB_FILE
import sqlite3

# HSN codes for medical services
HSN_MAP = {
    "ECG": "998611", "Echo": "998611", "TMT": "998611",
    "OPD": "998311", "X-Ray": "998612", "Ultrasound": "998612",
    "Lab": "998613", "Pharmacy": "300490", "Consultation": "998311",
    "IPD": "998311", "Emergency": "998311",
}

SAC_MEDICAL = "998311"  # Medical services
SAC_DIAGNOSTIC = "998611"  # Diagnostic services
SAC_PATHOLOGY = "998613"  # Pathology
SAC_PHARMACY = "300490"  # Medicines

GST_RATES = {
    "medical": 0.0,      # Healthcare is GST-exempt in India
    "diagnostic": 0.05,  # 5% GST (2.5% CGST + 2.5% SGST)
    "pharmacy": 0.12,    # 12% GST (6% CGST + 6% SGST)
    "other": 0.18,       # 18% GST (9% CGST + 9% SGST)
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gst_invoices (
                id TEXT PRIMARY KEY, bill_id TEXT, invoice_number TEXT UNIQUE,
                patient_name TEXT, patient_gst TEXT DEFAULT '',
                billing_date TEXT, total_amount REAL,
                taxable_amount REAL, cgst REAL, sgst REAL, igst REAL,
                cess REAL DEFAULT 0, tax_rate REAL,
                hsn_code TEXT, sac_code TEXT,
                is_einvoice INTEGER DEFAULT 0,
                irn TEXT DEFAULT '', status TEXT DEFAULT 'generated',
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gst_returns (
                id TEXT PRIMARY KEY, return_type TEXT NOT NULL,
                period TEXT NOT NULL, financial_year TEXT NOT NULL,
                filing_status TEXT DEFAULT 'pending',
                data TEXT DEFAULT '{}',
                filed_at TEXT, created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def get_hsn_for_test(test_name: str) -> str:
    return HSN_MAP.get(test_name, "998611")


def get_gst_rate(test_name: str) -> float:
    test_upper = test_name.lower() if test_name else ""
    if test_name == "Pharmacy":
        return GST_RATES["pharmacy"]
    elif test_name in ("OPD", "Consultation", "IPD", "Emergency"):
        return GST_RATES["medical"]  # exempt
    elif any(x in test_upper for x in ["ecg", "echo", "tmt", "x-ray", "ultrasound"]):
        return GST_RATES["diagnostic"]
    elif any(x in test_upper for x in ["lab", "blood", "urine", "pathology"]):
        return GST_RATES["diagnostic"]
    return GST_RATES["other"]


def calculate_tax(amount: float, tax_rate: float) -> dict:
    """Calculate CGST, SGST, and total tax."""
    if tax_rate == 0:
        return {"cgst": 0.0, "sgst": 0.0, "igst": 0.0, "total_tax": 0.0, "taxable": amount}
    half_rate = tax_rate / 2
    taxable = round(amount / (1 + tax_rate), 2)
    total_tax = round(amount - taxable, 2)
    cgst = round(total_tax / 2, 2)
    sgst = round(total_tax / 2, 2)
    return {"cgst": cgst, "sgst": sgst, "igst": 0.0, "total_tax": total_tax, "taxable": taxable}


def generate_gst_invoice(bill_id: str, patient_name: str, total_amount: float,
                         test_name: str = "Consultation", patient_gst: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        gst_rate = get_gst_rate(test_name)
        hsn = get_hsn_for_test(test_name)
        tax = calculate_tax(total_amount, gst_rate)
        inv_id = str(uuid.uuid4())
        inv_no = f"GST-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO gst_invoices (id, bill_id, invoice_number, patient_name, patient_gst,
                billing_date, total_amount, taxable_amount, cgst, sgst, igst, tax_rate,
                hsn_code, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (inv_id, bill_id, inv_no, patient_name, patient_gst,
              date.today().isoformat(), total_amount, tax["taxable"],
              tax["cgst"], tax["sgst"], tax["igst"], gst_rate,
              hsn, "generated", now))
        conn.commit()
        return {"success": True, "invoice_number": inv_no,
                "cgst": tax["cgst"], "sgst": tax["sgst"],
                "total_tax": tax["total_tax"], "taxable": tax["taxable"]}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_gst_invoices(month: int = 0, year: int = 0) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        m = month or date.today().month
        y = year or date.today().year
        start = f"{y}-{m:02d}-01"
        if m == 12:
            end = f"{y+1}-01-01"
        else:
            end = f"{y}-{m+1:02d}-01"
        cursor.execute("SELECT * FROM gst_invoices WHERE billing_date >= ? AND billing_date < ? ORDER BY created_at DESC",
                      (start, end))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_gst_summary(month: int = 0, year: int = 0) -> dict:
    invoices = get_gst_invoices(month, year)
    total_taxable = sum(i.get("taxable_amount", 0) for i in invoices)
    total_cgst = sum(i.get("cgst", 0) for i in invoices)
    total_sgst = sum(i.get("sgst", 0) for i in invoices)
    total_igst = sum(i.get("igst", 0) for i in invoices)
    return {
        "invoice_count": len(invoices),
        "total_taxable": total_taxable,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "total_tax": total_cgst + total_sgst + total_igst,
    }
