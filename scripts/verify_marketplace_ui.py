import requests
B = "https://gillhopitalsoftware1.pythonanywhere.com"

import time
for _ in range(10):
    r = requests.get(B + "/health", timeout=60)
    if r.status_code == 200:
        break
    time.sleep(5)

print("HEALTH:", r.status_code, r.json().get("build"))

r = requests.get(B + "/find-doctor", timeout=60)
t = r.text
print("free-text city input:", 'id="city" list="city-options"' in t)
print("free-text specialty input:", 'id="specialty" list="specialty-options"' in t)
print("no empty <select> for city:", '<select id="city"' not in t)

# doctors API still alive
r = requests.get(B + "/api/v1/marketplace/doctors", timeout=60)
print("doctors total:", r.json().get("total"))
