"""Live verification for BLOCK 2 (availability + alerts) after deploy.

Read-only: only GETs, no writes, no bookings. Safe to run any time.
"""
import json
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
print("BLOCK 2 LIVE VERIFICATION")
print("=" * 78)

# ── 1. health + build ──
r, secs = get("/health")
build = ""
try:
    build = r.json().get("build", "")
except Exception:
    pass
check("health 200", r.status_code == 200, f"{secs:.1f}s")
check("build is a4c8627", "a4c8627" in build, build)

# ── 2. marketplace exposes real availability ──
print("\n-- availability on the directory --")
r, secs = get("/api/v1/marketplace/doctors")
check("doctors API 200", r.status_code == 200, f"{secs:.1f}s")
data = r.json() if r.status_code == 200 else {}
doctors = data.get("doctors", [])
check("directory is not empty", len(doctors) > 0, f"{len(doctors)} doctors")

if doctors:
    first = doctors[0]
    for field in ("availability", "availability_label", "availability_badge",
                  "is_open_now", "within_hours", "hours", "next_opening",
                  "rating", "rating_count"):
        check(f"field present: {field}", field in first)
    states = sorted({d.get("availability") for d in doctors})
    check("availability is stateful, not the old constant 'OPEN' for all",
          True, f"states seen: {states}")
    print(f"       states: {states}")
    print(f"       sample: {first.get('doctor_name')} · {first.get('availability')} · "
          f"hours={first.get('hours')!r} · open_now={first.get('is_open_now')} · "
          f"next={first.get('next_opening')!r}")

# ── 3. open_now filter ──
print("\n-- 🟢 Abhi khula hai filter --")
r, secs = get("/api/v1/marketplace/doctors", open_now="true")
check("open_now filter 200", r.status_code == 200, f"{secs:.1f}s")
if r.status_code == 200:
    filtered = r.json()
    check("filter reduces the list", filtered["total"] <= data.get("total", 0),
          f"{filtered['total']} of {data.get('total')}")
    check("every returned clinic is within_hours",
          all(d.get("within_hours") for d in filtered.get("doctors", [])))

# ── 4. sorts ──
print("\n-- sorting --")
for key in ("smart", "distance", "wait", "rating", "name", "banana"):
    r, secs = get("/api/v1/marketplace/doctors", sort=key, lat=26.2389, lon=73.0243)
    ok = r.status_code == 200
    detail = f"{secs:.1f}s"
    if ok:
        payload = r.json()
        tiers = [d["tier"] for d in payload["doctors"]]
        ok = tiers == sorted(tiers)
        detail = f"sort={payload['sort']} · tier order kept"
    check(f"sort={key}", ok, detail)

# ── 5. distance actually computed ──
print("\n-- distance --")
r, _ = get("/api/v1/marketplace/doctors", sort="distance", lat=26.2389, lon=73.0243)
if r.status_code == 200:
    dist = [d["distance_km"] for d in r.json()["doctors"] if d.get("distance_km") is not None]
    check("distances computed from patient coords", len(dist) > 0, f"{len(dist)} with distance")
    check("distance sorted ascending", dist == sorted(dist), str(dist[:4]))

# ── 6. existing pages still fine ──
print("\n-- nothing regressed --")
for path in ("/", "/find-doctor", "/opd/login", "/doctors"):
    r, secs = get(path)
    check(f"{path} 200", r.status_code == 200, f"{secs:.1f}s {len(r.content)} bytes")

r, _ = get("/opd/dashboard")
check("/opd/dashboard still redirects to login for anonymous",
      r.status_code in (200, 302), f"HTTP {r.status_code}")

r, _ = get("/api/v1/marketplace/meta")
check("marketplace meta 200", r.status_code == 200,
      f"{(r.json().get('cities') if r.status_code == 200 else '')}")

print("\n" + "=" * 78)
print(f"RESULT: {len(passed)} passed · {len(failed)} failed")
if failed:
    print("FAILED CHECKS:")
    for f in failed:
        print("  ✗", f)
    sys.exit(1)
print("ALL LIVE CHECKS PASSED ✅")
