"""Live verification for BLOCK 7 (accuracy, ranking, reviews, referrals, network).

Read-only: GETs plus one unauthenticated probe of the auth-guarded routes.
No bookings, no reviews and no referrals are created, so running this against
production never touches real data.

Run:  python scripts/verify_block7_live.py
"""
import sys
import time

import requests

BASE = "https://gillhopitalsoftware1.pythonanywhere.com"
SEED_TOKEN = "GIL-DEMO-SEED-2026"

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
print("BLOCK 7 LIVE VERIFICATION")
print("=" * 78)

# ── 1. build ──
r, secs = get("/health")
build = ""
try:
    build = r.json().get("build", "")
except Exception:
    pass
check("health 200", r.status_code == 200, f"{secs:.1f}s")
check("build is 7e360ba", "7e360ba" in build, build)

# ── 2. F-04 / F-05 — tags + ranking score ──
print("\n-- F-04 / F-05 tags + rank_score --")
r, _ = get("/api/v1/marketplace/doctors")
doctors = r.json().get("doctors", []) if r.status_code == 200 else []
check("doctors API 200", r.status_code == 200, f"{len(doctors)} doctors")

if doctors:
    first = doctors[0]
    check("tags present", isinstance(first.get("tags"), list), str(first.get("tags"))[:70])
    check("tag_labels present", isinstance(first.get("tag_labels"), list))
    check("rank_score present", first.get("rank_score") is not None,
          str(first.get("rank_score")))
    check("rating fields present",
          all(k in first for k in ("rating", "rating_count")))

    tagged = [d for d in doctors if d.get("tags")]
    check("every clinic gets at least one tag", len(tagged) == len(doctors),
          f"{len(tagged)}/{len(doctors)}")
    all_tags = sorted({t for d in doctors for t in (d.get("tags") or [])})
    print(f"       tags seen: {all_tags}")

# ── 3. smart sort = score driven, tier first ──
print("\n-- smart sort is score-driven and tier-safe --")
r, _ = get("/api/v1/marketplace/doctors", sort="smart", lat=26.2389, lon=73.0243)
if r.status_code == 200:
    payload = r.json()
    tiers = [d["tier"] for d in payload["doctors"]]
    check("tier order kept", tiers == sorted(tiers), str(tiers))
    partner_scores = [d.get("rank_score") for d in payload["doctors"] if d["tier"] == 1]
    check("partner scores reported", all(s is not None for s in partner_scores),
          str(partner_scores[:4]))
    check("partners sorted by score descending",
          partner_scores == sorted(partner_scores, reverse=True),
          str(partner_scores[:4]))
else:
    check("smart sort 200", False, f"HTTP {r.status_code}")

for key in ("distance", "wait", "rating", "name"):
    r, _ = get("/api/v1/marketplace/doctors", sort=key, lat=26.2389, lon=73.0243)
    ok = r.status_code == 200
    if ok:
        tiers = [d["tier"] for d in r.json()["doctors"]]
        ok = tiers == sorted(tiers)
    check(f"sort={key} keeps tier order", ok)

# ── 4. F-07 — public verified reviews ──
print("\n-- F-07 verified reviews --")
if doctors:
    r, _ = get("/api/v1/reviews", clinic_id=doctors[0]["id"])
    check("reviews listing 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        payload = r.json()
        ok = all(k in payload for k in ("rating", "count", "reviews", "distribution"))
        check("reviews shape complete", ok, f"count={payload.get('count')}")
        blob = str(payload)
        # Reviews must never publish who visited.
        check("no patient identity in the listing",
              "CQ-" not in blob and "phone" not in blob.lower())

r, _ = get("/api/v1/reviews", clinic_id="00000000-0000-0000-0000-000000000000")
check("unknown clinic reviews 404", r.status_code == 404, f"HTTP {r.status_code}")

# ── 5. F-06 — referral slip ──
print("\n-- F-06 referral slip --")
r, _ = get("/r/not-a-real-token")
check("garbage slip token 404", r.status_code == 404, f"HTTP {r.status_code}")
r, _ = get("/r/eyJyaWQiOiJ4In0.aaaa.bbbb")
check("tampered slip token refused", r.status_code == 404, f"HTTP {r.status_code}")

# ── 6. F-08 — PHI-free network view ──
print("\n-- F-08 PHI-free network overview --")
r, _ = get("/api/v1/admin/network")
check("network requires auth", r.status_code == 401, f"HTTP {r.status_code}")

r, _ = get("/api/v1/admin/network", token=SEED_TOKEN)
check("network with seed token 200", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    payload = r.json()
    totals = payload["totals"]
    check("network totals present", totals.get("clinics", 0) >= 1, str(totals))
    check("phi_free flag set", payload.get("phi_free") is True)
    # Check the DATA only — the human note legitimately says the words.
    blob = str({"n": payload["nodes"], "t": totals}).lower()
    leaked = [k for k in ("patient_name", "patient_id", "phone", "diagnosis",
                          "prescription", "visit_id", "token_number") if k in blob]
    check("network payload is PHI-free", not leaked, f"leaked={leaked or 'none'}")

# ── 7. F-03 — accuracy route is guarded, not broken ──
print("\n-- F-03 accuracy route --")
r = requests.get(BASE + "/opd/api/stats/ewt-accuracy", timeout=45, allow_redirects=False)
check("accuracy route does not 500", r.status_code < 500, f"HTTP {r.status_code}")

# ── 8. private routes guarded ──
print("\n-- private routes guarded --")
for path in ("/opd/api/referrals", "/opd/api/slots", "/opd/api/queue-ewt"):
    r = requests.get(BASE + path, timeout=45, allow_redirects=False)
    check(f"{path} not 500", r.status_code < 500, f"HTTP {r.status_code}")

# ── 9. nothing regressed ──
print("\n-- nothing regressed --")
for path in ("/", "/find-doctor", "/opd/login", "/doctors", "/health"):
    r, secs = get(path)
    check(f"{path} 200", r.status_code == 200, f"{secs:.1f}s {len(r.content)} bytes")

r, _ = get("/api/v1/marketplace/doctors", open_now="true")
check("open_now filter still works", r.status_code == 200,
      f"{r.json().get('total')} open" if r.status_code == 200 else "")

print("\n" + "=" * 78)
print(f"RESULT: {len(passed)} passed · {len(failed)} failed")
if failed:
    print("FAILED CHECKS:")
    for name in failed:
        print("  ✗", name)
    sys.exit(1)
print("ALL LIVE CHECKS PASSED ✅")
