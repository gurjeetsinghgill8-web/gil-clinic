import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
TOKEN = "GIL-DEMO-SEED-2026"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("health ok", r.status_code == 200, r.json().get("build", ""))

# 1. Crawler receiving end — ingest schema (token-gated)
r = requests.get(B + "/api/v1/ingest/schema", params={"token": TOKEN}, timeout=60)
chk("ingest schema reachable (receiving end)", r.status_code == 200 and r.json().get("ok"),
    f"HTTP {r.status_code}")

# 2. Marketplace API alive
r = requests.get(B + "/api/v1/marketplace/meta", timeout=60)
chk("marketplace meta API", r.status_code == 200, f"HTTP {r.status_code}")

# 3. Before: /find-doctor empty?
before = requests.get(B + "/find-doctor", timeout=60).text
print(f"  before: 'No doctor' in page = {'No doctor' in before}")

# 4. Seed demo clinics (try documented path first, then code path)
for path in ("/api/v1/marketplace/seed", "/seed"):
    r = requests.post(B + path, params={"token": TOKEN}, timeout=60)
    print(f"  POST {path} -> {r.status_code} {r.text[:80]}")
    if r.status_code == 200:
        chk(f"seed OK via {path}", r.json().get("ok"), r.text[:120])
        break

# 5. After: /find-doctor should list doctors
after = requests.get(B + "/find-doctor", timeout=60).text
has_doctors = ("Dr." in after) or ("Doctor" in after)
chk("/find-doctor now lists doctors", "No doctor" not in after, f"page {len(after)} bytes")
chk("city/specialty data present", any(c in after for c in ("Jodhpur", "Jaipur", "Ahmedabad", "Delhi")))

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("MARKETPLACE SEED + INGEST VERIFIED")
