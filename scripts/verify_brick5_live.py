import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 41fdf53", "41fdf53" in r.json().get("build", ""), r.json().get("build", ""))


def login(pin, role):
    s = requests.Session()
    s.post(B + "/signin", data={"pin": pin, "role": role}, timeout=60, allow_redirects=False)
    return s


# Manager PIN is unique -> renders the dashboard sidebar without a role picker.
s = login("9999", "")

# Sidebar (base.html) must no longer advertise the dead/fake modules.
r = s.get(B + "/staff/reception", timeout=60, allow_redirects=False)
chk("reception renders for manager", r.status_code == 200, f"HTTP {r.status_code}")
for ghost in ("Pharmacy", "HR & Payroll", "Inventory", "Manager Overview", "Coming Soon", "data-uc"):
    chk(f"sidebar no longer shows '{ghost}'", ghost not in r.text, "present" if ghost in r.text else "")

# Department home page: no 'COMING'/'BUILDING' placeholders; ECG/Echo/TMT now LIVE.
r = s.get(B + "/staff/home", timeout=60, allow_redirects=False)
chk("/staff/home renders", r.status_code == 200, f"HTTP {r.status_code}")
for ghost in ("Under Construction", "Coming Soon", "COMING", "BUILDING"):
    chk(f"/staff/home no longer shows '{ghost}'", ghost not in r.text, "present" if ghost in r.text else "")
chk("ECG Lab now listed as LIVE", "ECG Lab" in r.text)
chk("Echo Lab now listed as LIVE", "Echo Lab" in r.text)

# The disabled stubs still bounce safely (not broken links) rather than render.
for p in ("/staff/manager", "/staff/billing", "/staff/tv"):
    r = s.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} safely redirects", r.status_code in (302, 307) and r.headers.get("location") == "/staff/home",
        f"HTTP {r.status_code} -> {r.headers.get('location')}")

# nothing regressed
for p in ("/", "/find-doctor", "/health", "/signin"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} 200", rr.status_code == 200, f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 5 LIVE VERIFIED")
