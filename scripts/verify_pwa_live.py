"""Live verification for the PWA fix + the /tools front door.

Read-only. Checks the exact requirements Chrome enforces for installability,
verifies that every declared icon actually FETCHES (declaring one is not the
same as serving one — that mismatch was the original bug), and confirms that
the private routes are still guarded.

Run:  python scripts/verify_pwa_live.py
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


def get(path, **kw):
    t = time.time()
    r = requests.get(BASE + path, timeout=60, **kw)
    return r, time.time() - t


print("=" * 78)
print("PWA + TOOLS LIVE VERIFICATION")
print("=" * 78)

r, secs = get("/health")
build = ""
try:
    build = r.json().get("build", "")
except Exception:
    pass
check("health 200", r.status_code == 200, f"{secs:.1f}s")
check("build is 3ffbe26", "3ffbe26" in build, build)

# ── Chrome's installability requirements ──
print("\n-- Chrome ke actual install requirements --")
r, _ = get("/manifest.json")
check("manifest served from root", r.status_code == 200, r.headers.get("content-type", ""))
check("manifest is not hard-cached", "no-cache" in r.headers.get("cache-control", ""))

manifest = {}
if r.status_code == 200:
    manifest = r.json()
    check("display standalone", manifest.get("display") == "standalone")
    check(
        "start_url inside scope",
        str(manifest.get("start_url", "")).startswith(manifest.get("scope", "/")),
    )
    sizes = sorted({i["sizes"] for i in manifest.get("icons", [])})
    check("192x192 declared", "192x192" in sizes, str(sizes))
    check("512x512 declared", "512x512" in sizes, str(sizes))
    check(
        "maskable declared",
        any(i.get("purpose") == "maskable" for i in manifest.get("icons", [])),
    )

    # The original bug: declared but 404. Declaring is not serving.
    print("  -- every declared icon must actually fetch --")
    for icon in manifest.get("icons", []):
        rr, _ = get(icon["src"])
        name = icon["src"].rsplit("/", 1)[-1]
        check(
            f"icon fetches: {name}",
            rr.status_code == 200
            and rr.headers.get("content-type", "").startswith("image/png")
            and len(rr.content) > 500,
            f"HTTP {rr.status_code} {len(rr.content)}b",
        )

# ── service worker ──
print("\n-- service worker --")
r, _ = get("/sw.js")
check("sw.js served from ROOT", r.status_code == 200, f"HTTP {r.status_code}")
check(
    "Service-Worker-Allowed: /",
    r.headers.get("service-worker-allowed") == "/",
    str(r.headers.get("service-worker-allowed")),
)
check("sw.js is not hard-cached", "no-cache" in r.headers.get("cache-control", ""))
if r.status_code == 200:
    source = r.text
    check("worker refuses to cache /track/", "'/track/'" in source)
    check("worker refuses to cache /opd/api/", "'/opd/api/'" in source)
    check("worker refuses to cache /my/", "'/my/'" in source)
    check("worker refuses to cache /card/", "'/card/'" in source)
    check("worker documents the shared-device reason", "shared" in source.lower())

# ── self-check endpoint ──
print("\n-- /pwa-status self-check --")
r, _ = get("/pwa-status")
check("pwa-status 200", r.status_code == 200)
if r.status_code == 200:
    payload = r.json()
    bad = [c["check"] for c in payload.get("checks", []) if not c["ok"]]
    check("reports installable", payload.get("installable") is True, str(bad) or "all checks pass")
    check("explains how to install", "Install" in payload.get("how_to_install", ""))
    check("states the no-patient-data-caching rule", "cache" in payload.get("note", "").lower())

# ── pages that must link the manifest ──
print("\n-- pages jo manifest link karte hain --")
for path in ("/", "/find-doctor", "/opd/login"):
    r, _ = get(path)
    linked = "manifest.json" in r.text if r.status_code == 200 else False
    check(f"{path} links manifest", linked, f"HTTP {r.status_code}")

# ── the front door ──
print("\n-- /tools (jo pehle reach nahi ho raha tha) --")
for path in ("/tools", "/opd/api/tools/summary"):
    r, _ = get(path, allow_redirects=False)
    guarded = r.status_code in (301, 302, 303, 307, 401, 403)
    check(f"{path} requires login (not 500)", guarded and r.status_code < 500, f"HTTP {r.status_code}")

# a staff-only read must still refuse an anonymous caller
for path in ("/api/v1/ingest/runs", "/api/v1/marketplace/opt-out"):
    r, _ = get(path)
    check(f"{path} refuses anonymous", r.status_code == 401, f"HTTP {r.status_code}")

# ── regressions ──
print("\n-- nothing regressed --")
for path in ("/", "/find-doctor", "/doctors", "/doctors/jodhpur", "/opd/login", "/health"):
    r, secs = get(path)
    check(f"{path} 200", r.status_code == 200, f"{secs:.1f}s {len(r.content)}b")

r, _ = get("/api/v1/marketplace/doctors")
check("doctors API 200", r.status_code == 200,
      f"{len(r.json().get('doctors', []))} doctors" if r.status_code == 200 else "")

print("\n" + "=" * 78)
print(f"RESULT: {len(passed)} passed · {len(failed)} failed")
if failed:
    print("FAILED CHECKS:")
    for name in failed:
        print("  ✗", name)
    sys.exit(1)
print("ALL LIVE CHECKS PASSED ✅")
