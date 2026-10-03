import requests
B = "https://gillhopitalsoftware1.pythonanywhere.com"
TOKEN = "GIL-DEMO-SEED-2026"

r = requests.get(B + "/health", timeout=60)
print("HEALTH:", r.json().get("build"))

# Seed route fix — /api/v1/marketplace/seed should now work (was 404 before)
r = requests.post(B + "/api/v1/marketplace/seed", params={"token": TOKEN}, timeout=60)
print("POST /api/v1/marketplace/seed ->", r.status_code, r.text[:80])

# Marketplace still alive?
r = requests.get(B + "/api/v1/marketplace/doctors", timeout=60)
j = r.json()
print("doctors:", j.get("total"), "| partners:", j.get("partners"))

# ingest receiving end still alive?
r = requests.get(B + "/api/v1/ingest/schema", params={"token": TOKEN}, timeout=60)
print("ingest schema:", r.status_code, r.json().get("ok"))
