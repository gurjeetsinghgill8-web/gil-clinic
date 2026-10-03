"""Audit helper 3: probe every concrete GET route against the live site.

A route that exists in code but 404s/500s when actually hit is the definition of
"page missing". This reports the real status of each, separating:

  * 200          — the page actually renders
  * 302/307      — redirects (usually to a login; listed with its Location)
  * 404          — a real dead page
  * 5xx          — a crash
  * param/skip   — paths with {vars} are probed with a sample value

Run:  python scripts/audit_probe_live.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "https://gillhopitalsoftware1.pythonanywhere.com"

routes = json.loads((ROOT / "scripts" / ".audit_routes.json").read_text(encoding="utf-8"))

# Sample values for path params, so a param route can still be probed.
SAMPLE = {
    "token": "sample-token",
    "public_token": "sample-token",
    "tracking_token": "sample-token",
    "uid": "sample-uid",
    "patient_id": "CQ-0000-000",
    "clinic_id": "00000000-0000-0000-0000-000000000000",
    "id": "0",
    "entry_id": "0",
    "review_id": "0",
    "reading_id": "0",
    "consent_id": "0",
    "lead_id": "0",
    "referral_id": "0",
    "city": "jodhpur",
    "service": "opd",
    "token_number": "1",
    "username": "sample",
}

GET_ONLY = {"GET"}

results = []
for r in routes:
    methods = r["methods"]
    if not (set(methods) & GET_ONLY):
        continue
    path = str(r["path"])
    if path in ("/openapi.json", "/docs", "/redoc") or path.endswith("/docs"):
        continue

    # Substitute path params with sample values; if a param has no sample, skip.
    concrete = path
    skip = False
    for m in re.finditer(r"\{([^}]+)\}", path):
        name = m.group(1)
        # strip type hint like {patient_id:path}
        name = name.split(":")[0]
        if name in SAMPLE:
            concrete = concrete.replace(m.group(0), SAMPLE[name], 1)
        else:
            skip = True
            break
    if skip:
        continue

    t = time.time()
    try:
        resp = requests.get(BASE + concrete, timeout=45, allow_redirects=False)
        status = resp.status_code
        loc = resp.headers.get("location", "")
        results.append(
            {
                "path": path,
                "probed": concrete,
                "status": status,
                "redirect_to": loc,
                "seconds": round(time.time() - t, 2),
            }
        )
    except Exception as e:
        results.append(
            {"path": path, "probed": concrete, "status": 0, "redirect_to": "", "error": f"{type(e).__name__}"}
        )

(ROOT / "scripts" / ".audit_probe.json").write_text(
    json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8"
)

# ── summary ──
from collections import Counter
buckets = Counter()
for r in results:
    s = r["status"]
    if s == 200:
        buckets["200 OK"] += 1
    elif s in (301, 302, 303, 307, 308):
        buckets[f"{s} redirect"] += 1
    elif s == 401:
        buckets["401 unauth"] += 1
    elif s == 404:
        buckets["404 NOT FOUND"] += 1
    elif s >= 500:
        buckets[f"{s} SERVER ERROR"] += 1
    elif s == 0:
        buckets["timeout/conn"] += 1
    else:
        buckets[f"{s} other"] += 1

print(f"probed {len(results)} GET routes")
for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]):
    print(f"  {v:>4}  {k}")

print("\n== 404 / 5xx / error (REAL PROBLEMS) ==")
for r in results:
    if r["status"] == 0 or r["status"] == 404 or r["status"] >= 500:
        print(f"  {r['status']}  {r['path']}  (probed {r['probed']})")

print("\n== redirects (to WHERE) ==")
redir = Counter(r["redirect_to"].split("?")[0] for r in results if r["status"] in (301, 302, 303, 307, 308) and r["redirect_to"])
for target, n in sorted(redir.items(), key=lambda kv: -kv[1]):
    print(f"  {n:>4} -> {target}")
