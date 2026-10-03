import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 14e06d4", "14e06d4" in r.json().get("build", ""), r.json().get("build", ""))

r = requests.get(B + "/signin", timeout=60)
chk("/signin page 200", r.status_code == 200 and "PIN" in r.text, f"HTTP {r.status_code} {len(r.content)}b")

r = requests.post(B + "/signin", data={"pin": "5554"}, timeout=60, allow_redirects=False)
chk(
    "PIN 5554 -> 303 /opd/dashboard + opd_session",
    r.status_code == 303
    and r.headers.get("location") == "/opd/dashboard"
    and "opd_session" in r.headers.get("set-cookie", ""),
    f"HTTP {r.status_code} -> {r.headers.get('location')}",
)

r = requests.post(B + "/signin", data={"pin": "1234"}, timeout=60, allow_redirects=False)
chk(
    "PIN 1234 -> role picker (not silent redirect)",
    r.status_code == 200 and "role" in r.text.lower() and "choice-btn" in r.text,
    f"HTTP {r.status_code}",
)

r = requests.post(B + "/signin", data={"pin": "5678"}, timeout=60, allow_redirects=False)
chk(
    "PIN 5678 -> 303 /staff/doctor + gc_session",
    r.status_code == 303
    and r.headers.get("location") == "/staff/doctor"
    and "gc_session" in r.headers.get("set-cookie", ""),
    f"HTTP {r.status_code} -> {r.headers.get('location')}",
)

r = requests.get(B + "/signin/check", params={"pin": "1234"}, timeout=60)
chk("check 1234 ambiguous", r.json().get("ambiguous") is True, f"{r.json().get('count')} roles")

for p in ("/opd/login", "/staff/login", "/clinic-portal", "/admin/login"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} still works (200/30x)", rr.status_code in (200, 301, 302, 303, 307, 308), f"HTTP {rr.status_code}")

r = requests.get(B + "/login", timeout=60)
chk("landing offers /signin", 'href="/signin"' in r.text, "")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 2a LIVE VERIFIED")
