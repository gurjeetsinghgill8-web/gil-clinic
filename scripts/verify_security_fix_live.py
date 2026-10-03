import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 66e48cd", "66e48cd" in r.json().get("build", ""), r.json().get("build", ""))

# ── Reception alone must never reach OPD ──────────────────────────────────────
s = requests.Session()
s.post(B + "/signin", data={"pin": "1234", "role": "reception"}, timeout=60, allow_redirects=False)

r = s.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("reception blocked from /opd/dashboard", r.status_code == 302 and "opd/login" in r.headers.get("location", ""),
    f"HTTP {r.status_code} -> {r.headers.get('location')}")

r = s.get(B + "/opd/api/settings", timeout=60, allow_redirects=False)
chk("reception blocked from /opd/api/settings", r.status_code == 302 and "opd/login" in r.headers.get("location", ""),
    f"HTTP {r.status_code}")

r = s.get(B + "/staff/doctor", timeout=60, allow_redirects=False)
chk("reception bounced off /staff/doctor -> /home",
    r.status_code == 302 and r.headers.get("location") == "/home",
    f"HTTP {r.status_code} -> {r.headers.get('location')}")

# ── Cookie stacking: doctor session must NOT survive a reception login ───────
s2 = requests.Session()
s2.post(B + "/signin", data={"pin": "5554", "role": ""}, timeout=60, allow_redirects=False)  # chief doctor
r = s2.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("doctor can open OPD first (sanity)", r.status_code == 200, f"HTTP {r.status_code}")

# Now the SAME browser logs in as reception — must clear the doctor cookie.
s2.post(B + "/signin", data={"pin": "1234", "role": "reception"}, timeout=60, allow_redirects=False)
r = s2.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("doctor session cleared after reception login",
    r.status_code == 302 and "opd/login" in r.headers.get("location", ""),
    f"HTTP {r.status_code} -> {r.headers.get('location')}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("SECURITY FIX LIVE VERIFIED")
