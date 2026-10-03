import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build c63a363", "c63a363" in r.json().get("build", ""), r.json().get("build", ""))

# Old login GET pages remain shims to /signin (routes intact, templates gone).
for p in ("/opd/login", "/staff/login", "/clinic-portal", "/admin/login"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"GET {p} -> /signin", rr.status_code in (302, 307) and rr.headers.get("location") == "/signin",
        f"HTTP {rr.status_code} -> {rr.headers.get('location')}")

# A failed OPD PIN login now renders the unified door, not the deleted template.
rr = requests.post(B + "/opd/login", data={"pin": "000000"}, timeout=60, allow_redirects=False)
chk("POST /opd/login -> unified login (401)", rr.status_code == 401, f"HTTP {rr.status_code}")
chk("unified login body (PIN door)", "Ek PIN" in rr.text and "GIL CLINIC" in rr.text)

# A failed admin username/password login renders the unified password tab.
rr = requests.post(B + "/admin/login", data={"username": "no_such_user_x", "password": "nope"}, timeout=60, allow_redirects=False)
chk("POST /admin/login -> unified login (401)", rr.status_code == 401, f"HTTP {rr.status_code}")
chk("unified password tab present", "Username + Password" in rr.text)

# A failed staff PIN login renders the unified door.
rr = requests.post(B + "/staff/login", data={"role": "reception", "name": "x", "pin": "999999"}, timeout=60, allow_redirects=False)
chk("POST /staff/login -> unified login", rr.status_code in (200, 401, 400), f"HTTP {rr.status_code}")
chk("staff error shows unified door", "Ek PIN" in rr.text or "GIL CLINIC" in rr.text)

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 7 LIVE VERIFIED")
