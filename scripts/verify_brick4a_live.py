import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"
ok, bad = [], []


def chk(n, c, d=""):
    (ok if c else bad).append(n)
    print(f"  [{'OK ' if c else 'FAIL'}] {n}{(' - ' + d) if d else ''}")


r = requests.get(B + "/health", timeout=60)
chk("build 6c00886", "6c00886" in r.json().get("build", ""), r.json().get("build", ""))


def login(role_pin_role):
    """Returns a session logged in as the given staff role via the unified door."""
    pin, role = role_pin_role
    s = requests.Session()
    s.post(B + "/signin", data={"pin": pin, "role": role}, timeout=60, allow_redirects=False)
    return s


# A receptionist must be bounced OFF /staff/lab and /staff/ecg.
s = login(("1234", "reception"))
r = s.get(B + "/staff/lab", timeout=60, allow_redirects=False)
chk("reception -> /staff/lab bounced to /home",
    r.status_code == 302 and r.headers.get("location") == "/home",
    f"HTTP {r.status_code} -> {r.headers.get('location')}")
r = s.get(B + "/staff/ecg", timeout=60, allow_redirects=False)
chk("reception -> /staff/ecg bounced to /home",
    r.status_code == 302 and r.headers.get("location") == "/home",
    f"HTTP {r.status_code}")

# A receptionist IS allowed into reception.
r = s.get(B + "/staff/reception", timeout=60, allow_redirects=False)
chk("reception -> /staff/reception allowed", r.status_code == 200, f"HTTP {r.status_code}")

# A lab tech is allowed into lab.
s = login(("1234", "lab"))
r = s.get(B + "/staff/lab", timeout=60, allow_redirects=False)
chk("lab -> /staff/lab allowed", r.status_code == 200, f"HTTP {r.status_code}")
r = s.get(B + "/staff/reception", timeout=60, allow_redirects=False)
chk("lab -> /staff/reception bounced", r.status_code == 302 and r.headers.get("location") == "/home")

# The hub no longer advertises the dead billing/tv modules (manager session).
s = login(("9999", ""))  # manager PIN, unique → no role picker needed
r = s.get(B + "/home", timeout=60, allow_redirects=False)
if r.status_code == 200:
    chk("hub does not advertise Billing/TV", "Billing" not in r.text and "TV Display" not in r.text)

# nothing regressed
for p in ("/", "/find-doctor", "/health", "/signin"):
    rr = requests.get(B + p, timeout=60, allow_redirects=False)
    chk(f"{p} 200", rr.status_code == 200, f"HTTP {rr.status_code}")

print()
print(f"RESULT: {len(ok)} passed, {len(bad)} failed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("BRICK 4a LIVE VERIFIED")
