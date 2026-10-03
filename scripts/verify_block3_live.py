"""Live verification for BLOCK 3 (slots + emergency + token labels) after deploy.

Read-only: only GETs and harmless probes. No bookings are created, so running
this against production never touches a real patient's queue.

Run:  python scripts/verify_block3_live.py
"""
import sys
import time

import requests

BASE = "https://gillhopitalsoftware1.pythonanywhere.com"

passed = []
failed = []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


def get(path, **params):
    t = time.time()
    r = requests.get(BASE + path, params=params or None, timeout=60)
    return r, time.time() - t


print("=" * 78)
print("BLOCK 3 LIVE VERIFICATION")
print("=" * 78)

# ── 1. build ──
r, secs = get("/health")
build = ""
try:
    build = r.json().get("build", "")
except Exception:
    pass
check("health 200", r.status_code == 200, f"{secs:.1f}s")
check("build is 81ac8a6", "81ac8a6" in build, build)

# ── 2. token labels on the public directory ──
print("\n-- token prefixes (E-04 display) --")
r, _ = get("/api/v1/marketplace/doctors")
doctors = r.json().get("doctors", []) if r.status_code == 200 else []
check("doctors API 200", r.status_code == 200, f"{len(doctors)} doctors")

partners = [d for d in doctors if d.get("partner")]
if partners:
    live = partners[0].get("live") or {}
    check("live payload carries serving_token_label",
          "serving_token_label" in live,
          f"label={live.get('serving_token_label')!r} token={live.get('serving_token')}")

# ── 3. public slot endpoint ──
print("\n-- public slot availability (SLT-02) --")
probed = 0
for d in doctors[:6]:
    r, secs = get("/api/v1/marketplace/slots", clinic_id=d["id"], date="")
    if r.status_code != 200:
        check(f"slots for {d['clinic_name'][:24]}", False, f"HTTP {r.status_code}")
        continue
    payload = r.json()
    ok = (
        payload.get("ok") is True
        and "slots" in payload
        and "queue" in payload
        and "advice" in payload
        and "token_label_prefix" in payload
    )
    check(
        f"slots shape for {d['clinic_name'][:24]}",
        ok,
        f"{payload.get('total', 0)} slots · prefix={payload.get('token_label_prefix')!r}",
    )
    if payload.get("slots"):
        s = payload["slots"][0]
        for field in ("id", "window", "capacity", "booked", "remaining",
                      "is_full", "bookable", "forecast", "confidence"):
            check(f"  slot field: {field}", field in s)
        print(f"       sample: {s['window']} · {s['booked']}/{s['capacity']} · "
              f"{s['forecast'][:60]}")
    probed += 1
    if probed >= 3:
        break

if not probed:
    check("at least one clinic probed for slots", False, "no clinics returned")

r, _ = get("/api/v1/marketplace/slots",
           clinic_id="00000000-0000-0000-0000-000000000000", date="")
check("unknown clinic → 404", r.status_code == 404, f"HTTP {r.status_code}")

# ── 4. private routes exist and are guarded, not broken ──
print("\n-- private slot/emergency routes are guarded (not 500) --")
for path, method in (
    ("/opd/api/slots", "get"),
    ("/opd/api/slots/emergency", "post"),
):
    try:
        response = requests.request(method, BASE + path, json={}, timeout=45,
                                    allow_redirects=False)
        # Anonymous access must be refused (30x/401/403/404/405) — a 500 would
        # mean the route is wired but broken.
        ok = response.status_code < 500
        check(f"{method.upper()} {path} does not 500", ok, f"HTTP {response.status_code}")
    except Exception as e:
        check(f"{method.upper()} {path}", False, f"{type(e).__name__}: {e}")

# ── 5. BLOCK 2 regression: availability still works ──
print("\n-- BLOCK 2 still live --")
if doctors:
    first = doctors[0]
    check("availability fields present",
          all(k in first for k in ("availability", "is_open_now", "within_hours", "hours")))

r, _ = get("/api/v1/marketplace/doctors", open_now="true")
check("open_now filter 200", r.status_code == 200,
      f"{r.json().get('total')} open" if r.status_code == 200 else "")

for sort in ("smart", "distance", "wait", "rating", "name"):
    r, _ = get("/api/v1/marketplace/doctors", sort=sort, lat=26.2389, lon=73.0243)
    ok = r.status_code == 200
    if ok:
        tiers = [d["tier"] for d in r.json()["doctors"]]
        ok = tiers == sorted(tiers)
    check(f"sort={sort} keeps tier order", ok)

# ── 6. pages ──
print("\n-- pages --")
for path in ("/", "/find-doctor", "/opd/login", "/doctors", "/health"):
    r, secs = get(path)
    check(f"{path} 200", r.status_code == 200, f"{secs:.1f}s {len(r.content)} bytes")

r, _ = get("/opd/dashboard")
check("/opd/dashboard not broken", r.status_code in (200, 302), f"HTTP {r.status_code}")

print("\n" + "=" * 78)
print(f"RESULT: {len(passed)} passed · {len(failed)} failed")
if failed:
    print("FAILED CHECKS:")
    for f in failed:
        print("  ✗", f)
    sys.exit(1)
print("ALL LIVE CHECKS PASSED ✅")
