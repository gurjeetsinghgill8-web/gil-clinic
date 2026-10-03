import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 2b8d410", "2b8d410" in r.json().get("build", ""), r.json().get("build", ""))

# The four old login pages are now shims to /signin.
for path in ("/opd/login", "/staff/login", "/clinic-portal", "/admin/login"):
    rr = requests.get(B + path, timeout=60, allow_redirects=False)
    chk(
        f"{path} -> 302 /signin (shim)",
        rr.status_code == 302 and rr.headers.get("location") == "/signin",
        f"HTTP {rr.status_code} -> {rr.headers.get('location')}",
    )

# The unified door still works end to end.
r = requests.get(B + "/signin", timeout=60)
chk("/signin 200", r.status_code == 200, f"{len(r.content)}b")
r = requests.post(B + "/signin", data={"pin": "5554"}, timeout=60, allow_redirects=False)
chk("PIN 5554 -> opd dashboard", r.status_code == 303 and r.headers.get("location") == "/opd/dashboard")
r = requests.post(B + "/signin/password", data={"username": "__nobody__", "password": "x"}, timeout=60, allow_redirects=False)
chk("password door still wired (401)", r.status_code == 401)

# A logged-in user who hits /opd/login would be sent to the dashboard — but an
# anonymous one follows the shim, which is the correct new behaviour.
r = requests.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("opd dashboard guard -> login (302)", r.status_code == 302 and "opd/login" in r.headers.get("location", ""))

# manifest start_url updated
r = requests.get(B + "/manifest.json", timeout=60)
chk("manifest start_url is /signin", r.json().get("start_url") == "/signin", r.json().get("start_url"))

# nothing else regressed
for p in ("/", "/find-doctor", "/doctors", "/health"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} 200", rr.status_code == 200, f"HTTP {rr.status_code}")

# /tools is staff-authenticated, so a 302 (to login) is correct, not a regression.
rr = requests.get(B + "/tools", timeout=60, allow_redirects=False)
chk("/tools guarded (302, not 500)", rr.status_code == 302, f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 2c LIVE VERIFIED")
