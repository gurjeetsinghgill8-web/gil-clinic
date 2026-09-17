"""Live PA DB se ek patient ki search-string + phone + reading count (privacy: sirf JSON)."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tok = open(os.path.join(ROOT, "pa_token.txt")).read().strip()
H = {"Authorization": "Token " + tok}
U = ("https://www.pythonanywhere.com/api/v0/user/gillhopitalsoftware1/files/path"
     "/home/gillhopitalsoftware1/gil-clinic/ghos_prod.db")

out = {"ok": False, "msg": ""}
try:
    r = requests.get(U, headers=H, timeout=120)
    if not r.ok or len(r.content) < 2000:
        out["msg"] = f"db download {r.status_code}"
    else:
        tmp = os.path.join(tempfile.gettempdir(), "gil_pa_info.db")
        with open(tmp, "wb") as fh:
            fh.write(r.content)
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        row = cur.execute(
            "SELECT name, phone, patient_id FROM patients ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        readings = cur.execute("SELECT COUNT(*) FROM patient_readings").fetchone()[0]
        con.close()
        os.remove(tmp)
        if row and row[0]:
            name = row[0]
            phone = "".join(ch for ch in (row[1] or "") if ch.isdigit())[-10:]
            out = {
                "ok": bool(phone),
                "msg": "" if phone else "patient ke paas 10-digit mobile nahi hai",
                "search": name.split(" ")[0][:6] if name else "",  # 4+ chars -> search chalti hai
                "phone": phone,
                "readings": int(readings or 0),
            }
        else:
            out["msg"] = "patients table khali"
except Exception as e:  # pragma: no cover
    out["msg"] = str(e)

print(json.dumps(out))
