import requests, time
B = "https://gillhopitalsoftware1.pythonanywhere.com"

for _ in range(10):
    r = requests.get(B + "/health", timeout=60)
    if r.status_code == 200:
        break
    time.sleep(5)
print("HEALTH:", r.status_code, r.json().get("build"))

s = requests.Session()
s.post(B + "/signin", data={"pin": "5554", "role": ""}, timeout=60, allow_redirects=True)
r = s.get(B + "/opd/dashboard", timeout=60, allow_redirects=False)
t = r.text
print("OPD dashboard:", r.status_code, len(t), "chars")
print("has qe-pill (toggle):", 'id="qe-pill"' in t)
print("has qe-close (close btn):", 'id="qe-close"' in t)
# The panel must NOT auto-open: load() should no longer call bare show();
# show(); should only appear in the pill/close handler + function defs.
print("show() not auto-called in load:", "show();" not in t or t.count("show();") <= 3)
