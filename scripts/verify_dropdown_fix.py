import requests, time
B = "https://gillhopitalsoftware1.pythonanywhere.com"

for _ in range(10):
    r = requests.get(B + "/health", timeout=60)
    if r.status_code == 200:
        break
    time.sleep(5)
print("HEALTH:", r.status_code, r.json().get("build"))

# Department page (ECG) — check the WhatsApp dropdown now opens upward
s = requests.Session()
s.post(B + "/signin", data={"pin": "1234", "role": "ecg"}, timeout=60, allow_redirects=True)
r = s.get(B + "/staff/ecg", timeout=60, allow_redirects=False)
t = r.text
print("ECG page:", r.status_code, len(t), "chars")
print("wa-menu opens upward (bottom:100%):", 'bottom:100%' in t and 'id="wa-menu"' in t)
print("no downward top:100% on wa-menu:", 'top:100%' not in t)
