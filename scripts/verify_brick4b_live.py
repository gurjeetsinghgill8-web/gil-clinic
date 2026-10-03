import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 997d783", "997d783" in r.json().get("build", ""), r.json().get("build", ""))

s = requests.Session()
s.post(B + "/signin", data={"pin": "5554", "role": ""}, timeout=60, allow_redirects=True)
r = s.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("opd dashboard 200", r.status_code == 200, f"HTTP {r.status_code}")

# Each partial must have rendered — markers from head, sidebar, main, scripts.
markers = [
    ("head partial (manifest)", 'rel="manifest"'),
    ("head partial (service worker)", "serviceWorker"),
    ("sidebar partial (Home link)", "Home / My Modules"),
    ("sidebar partial (New Rx)", "New Rx"),
    ("main partial (stats bar)", "Today's Patients"),
    ("main partial (prescription)", "New Prescription"),
    ("scripts partial (tab switch)", "TAB SWITCHING"),
]
for name, needle in markers:
    chk(name, needle in r.text, "present" if needle in r.text else "missing")

# The rendered page must be substantial (full dashboard, not a broken shell).
chk("full page rendered (~>200KB)", len(r.text) > 200000, f"{len(r.text)} chars")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 4b LIVE VERIFIED")
