import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"

r = requests.get(B + "/health", timeout=60)
print("HEALTH:", r.json().get("build"), "|", r.json().get("status"))

r = requests.get(B + "/find-doctor", timeout=60)
t = r.text
print("FIND-DOCTOR:", r.status_code, len(t), "bytes")
# is it empty / showing placeholder?
for kw in ("No doctor", "koi doctor", "0 doctors", "empty", "demo", "Jodhpur", "Dr."):
    if kw.lower() in t.lower():
        print("   contains:", kw)

# landing page — any visible version/build?
r = requests.get(B + "/", timeout=60)
t = r.text
print("LANDING:", r.status_code, len(t), "bytes")
for kw in ("version", "v2.0", "Build", "build", "2026"):
    if kw.lower() in t.lower():
        print("   contains:", kw)
