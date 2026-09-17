"""Live PA cleanup: test reading(s) delete + share snapshot refresh (production saaf)."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://gillhopitalsoftware1.pythonanywhere.com"
tok = open(os.path.join(ROOT, "pa_token.txt")).read().strip()
H = {"Authorization": "Token " + tok}
DB_URL = ("https://www.pythonanywhere.com/api/v0/user/gillhopitalsoftware1/files/path"
          "/home/gillhopitalsoftware1/gil-clinic/ghos_prod.db")


def db_snapshot() -> dict:
    r = requests.get(DB_URL, headers=H, timeout=120)
    if not r.ok:
        return {"error": f"db {r.status_code}"}
    tmp = os.path.join(tempfile.gettempdir(), "gil_pa_cleanup.db")
    with open(tmp, "wb") as fh:
        fh.write(r.content)
    con = sqlite3.connect(tmp)
    cur = con.cursor()
    link = cur.execute(
        "SELECT token, patient_id, patient_name FROM patient_portal_links ORDER BY id DESC LIMIT 1"
    ).fetchone()
    patient = cur.execute(
        "SELECT phone FROM patients ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    readings = cur.execute("SELECT COUNT(*) FROM patient_readings").fetchone()[0]
    shares = cur.execute("SELECT COUNT(*) FROM patient_shares").fetchone()[0]
    con.close()
    os.remove(tmp)
    return {
        "token": link[0] if link else "",
        "patient_id": link[1] if link else "",
        "phone": "".join(ch for ch in ((patient or [""])[0] or "") if ch.isdigit())[-10:],
        "readings": int(readings or 0),
        "shares": int(shares or 0),
    }


def main() -> int:
    before = db_snapshot()
    print("before:", json.dumps({k: v for k, v in before.items() if k != "token"}))
    token, phone = before.get("token"), before.get("phone")
    if not token or not phone:
        print("token/phone nahi mile - kuch nahi kiya")
        return 1

    s = requests.Session()
    v = s.post(f"{BASE}/my/{token}/verify", json={"phone": phone}, timeout=60)
    print("verify:", v.status_code, v.text[:80])
    if v.status_code != 200:
        return 1

    data = s.get(f"{BASE}/my/{token}/data", timeout=60).json()
    readings = data.get("readings") or []
    print("readings mili:", len(readings))
    for r in readings:
        d = s.delete(f"{BASE}/my/{token}/readings/{r['reading_id']}", timeout=60)
        print("  delete", r["reading_id"][:8], r.get("label"), r.get("value"), "->", d.status_code)

    # share snapshot ko refresh karo (wahi token, ab khali readings ke saath)
    sh = s.post(f"{BASE}/my/{token}/share", json={"note": "", "reuse": True}, timeout=60)
    print("share refresh:", sh.status_code, (sh.json().get("url", "")[:60] if sh.ok else sh.text[:120]))

    after = db_snapshot()
    print("after :", json.dumps({k: v for k, v in after.items() if k != "token"}))
    clean = after.get("readings") == 0
    print("PRODUCTION CLEAN:", clean)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
