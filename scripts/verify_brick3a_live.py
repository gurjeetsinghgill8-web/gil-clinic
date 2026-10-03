import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 794d782", "794d782" in r.json().get("build", ""), r.json().get("build", ""))

# /home requires a session → redirects to the unified door when anonymous.
r = requests.get(B + "/home", timeout=60, allow_redirects=False)
chk("/home -> 302 /signin (anonymous)", r.status_code == 302 and r.headers.get("location") == "/signin",
    f"HTTP {r.status_code} -> {r.headers.get('location')}")

# Log in as chief (opd_session), then /home must show doctor modules.
s = requests.Session()
r = s.post(B + "/signin", data={"pin": "5554"}, timeout=60, allow_redirects=False)
chk("login as chief (303)", r.status_code == 303)
r = s.get(B + "/home", timeout=60, allow_redirects=False)
chk("chief /home 200", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    chk("doctor sees OPD module", "Doctor OPD" in r.text)
    chk("doctor does NOT see admin panel", "Admin Panel" not in r.text)
    chk("doctor does NOT see lab", ">Lab<" not in r.text)

# A manager (staff gc_session) must see reception but not admin panel.
s2 = requests.Session()
r = s2.post(B + "/signin", data={"pin": "9999"}, timeout=60, allow_redirects=False)  # manager PIN
chk("login as manager (303)", r.status_code == 303)
r = s2.get(B + "/home", timeout=60, allow_redirects=False)
if r.status_code == 200:
    chk("manager sees reception", "Reception" in r.text)
    chk("manager does NOT see admin panel", "Admin Panel" not in r.text)

# nothing regressed
for p in ("/", "/find-doctor", "/doctors", "/health", "/signin"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} 200", rr.status_code == 200, f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 3a LIVE VERIFIED")
