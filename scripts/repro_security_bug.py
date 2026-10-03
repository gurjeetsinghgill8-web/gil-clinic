import sys
import requests

B = "https://gillhopitalsoftware1.pythonanywhere.com"


def login(pin, role):
    s = requests.Session()
    s.post(B + "/signin", data={"pin": pin, "role": role}, timeout=60, allow_redirects=False)
    return s


def probe(s, path, method="GET", **kw):
    try:
        if method == "GET":
            r = s.get(B + path, timeout=60, allow_redirects=False, **kw)
        else:
            r = s.post(B + path, timeout=60, allow_redirects=False, **kw)
        # show a leak only when we actually get content (not a redirect)
        body = r.text[:200].replace("\n", " ")
        print(f"  {method} {path:40s} -> {r.status_code}  loc={r.headers.get('location','-')[:40]!r}  {body[:120]!r}")
        return r
    except Exception as e:
        print(f"  {method} {path:40s} -> ERROR {e}")
        return None


print("=== RECEPTION (PIN 1234, role=reception) ===")
s = login("1234", "reception")
probe(s, "/staff/reception")           # allowed: own room
probe(s, "/staff/opd")                 # should be BLOCKED (reception not doctor)
probe(s, "/staff/doctor")              # redirects to /opd/dashboard?
probe(s, "/opd/dashboard")             # the doctor cockpit — should be BLOCKED
probe(s, "/opd/api/settings")          # doctor AI keys — should be BLOCKED
probe(s, "/opd/api/queue-ewt")         # queue feed
probe(s, "/opd/api/referrals")         # referral data
probe(s, "/opd/api/leads")             # growth leads
probe(s, "/opd/api/patient-report", method="GET", params={"patient_id": "CQ-0000-000"})

print()
print("=== LAB (PIN 1234, role=lab) ===")
s2 = login("1234", "lab")
probe(s2, "/opd/dashboard")
probe(s2, "/opd/api/settings")

print()
print("=== DOCTOR (PIN 5678, role=doctor) ===")
s3 = login("5678", "")
probe(s3, "/staff/doctor")
probe(s3, "/opd/dashboard")
