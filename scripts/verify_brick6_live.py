import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 672bf8e", "672bf8e" in r.json().get("build", ""), r.json().get("build", ""))


def signin(pin, role=""):
    s = requests.Session()
    s.post(B + "/signin", data={"pin": pin, "role": role}, timeout=60, allow_redirects=True)
    return s


# Staff dashboard (manager) — topbar Home link.
s = signin("9999", "")
r = s.get(B + "/staff/reception", timeout=60, allow_redirects=False)
chk("staff reception 200", r.status_code == 200, f"HTTP {r.status_code}")
chk("staff topbar has /home link", 'href="/home"' in r.text and "🏠 Home" in r.text)

# OPD dashboard (chief) — sidebar Home/My Modules link.
s = signin("5554", "")
r = s.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
chk("opd dashboard 200", r.status_code == 200, f"HTTP {r.status_code}")
chk("opd sidebar has /home link", 'href="/home"' in r.text and "Home / My Modules" in r.text)

# Regression.
for p in ("/", "/signin", "/health", "/home"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} reachable", rr.status_code in (200, 302, 307), f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 6 LIVE VERIFIED")
