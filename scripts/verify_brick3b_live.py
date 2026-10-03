import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build a148414", "a148414" in r.json().get("build", ""), r.json().get("build", ""))

# Log in as chief, then fetch the OPD dashboard HTML and confirm it links /home.
s = requests.Session()
s.post(B + "/signin", data={"pin": "5554"}, timeout=60, allow_redirects=False)
r = s.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("opd dashboard renders for chief", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    chk("opd dashboard links /home (My Modules)", 'href="/home"' in r.text and "My Modules" in r.text)

# Log in as reception (staff), fetch a staff page, confirm it inherits the link.
s2 = requests.Session()
s2.post(B + "/signin", data={"pin": "1234", "role": "reception"}, timeout=60, allow_redirects=False)
r = s2.get(B + "/staff/reception", timeout=60, allow_redirects=False)
chk("staff reception renders", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    chk("staff page links /home (My Modules)", 'href="/home"' in r.text and "My Modules" in r.text)

# The hub still works end to end.
r = s.get(B + "/home", timeout=60, allow_redirects=False)
chk("chief /home still 200", r.status_code == 200, f"HTTP {r.status_code}")

# nothing regressed
for p in ("/", "/find-doctor", "/health", "/signin"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} 200", rr.status_code == 200, f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 3b LIVE VERIFIED")
