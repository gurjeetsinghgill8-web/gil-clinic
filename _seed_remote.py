"""One-off: remote PythonAnywhere par demo clinics seed karo (scheduled task)."""
import datetime as _dt
import sys
import time

import requests

USERNAME = "gillhopitalsoftware1"
V0 = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}"
token = open("pa_token.txt").read().strip()
H = {"Authorization": f"Token {token}"}

VENV = "/home/gillhopitalsoftware1/.virtualenvs/gilclinic/bin/python"
LOG = "/home/gillhopitalsoftware1/pa_seed.log"
cmdline = (
    f"cd /home/{USERNAME}/gil-clinic && "
    f"{VENV} scripts/seed_marketplace_demo.py > {LOG} 2>&1"
)

at = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=2)
r = requests.post(V0 + "/schedule/", headers=H, timeout=60, json={
    "command": cmdline, "enabled": True,
    "interval": "daily", "hour": at.hour, "minute": at.minute,
})
print("SEED TASK:", r.status_code, (r.json() if r.ok else r.text[:300]))
task_id = (r.json() or {}).get("id") if r.ok else None

if not r.ok:
    sys.exit(1)

print(f"task {at.strftime('%H:%M')} UTC par chalega — intezaar ~3.5 min...")
time.sleep(210)

lg = requests.get(V0 + "/files/path" + LOG, headers=H, timeout=60)
print("SEED LOG:", lg.status_code)
if lg.ok:
    print(lg.content.decode("utf-8", "replace")[-600:])

if task_id is not None:
    d = requests.delete(V0 + f"/schedule/{task_id}/", headers=H, timeout=60)
    print("TASK DELETE:", d.status_code)
