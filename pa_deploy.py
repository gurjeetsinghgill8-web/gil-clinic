#!/usr/bin/env python3
# pa_deploy.py - GIL CLINIC PythonAnywhere deploy driver (runs from the laptop).
#
# Uses the PythonAnywhere API directly (same endpoints as the official `pa` CLI):
#   - v0: files, classic webapps, schedule, cpu
#   - v1: websites (ASGI beta)
#
# Token is read from pa_token.txt next to this script (gitignored - NEVER commit it).
# Local state (secret, generated passwords) lives in pa_state.json (gitignored).
#
# Subcommands:
#   status                - current account state (cpu, webapps, websites, schedule)
#   bootstrap             - upload setup.sh + .env + bootstrap WSGI file
#   webapp_create         - create the temporary classic WSGI webapp (exec vehicle)
#   trigger               - hit the secret URL to start setup.sh in background
#   log                   - tail the remote setup log
#   webapp_delete         - delete the temporary classic webapp
#   site_create           - create the real ASGI website (uvicorn command)
#   site_get / site_reload
#   upload_db             - upload local patient DB to remote ghos_prod.db
#   backup_task           - create daily backup scheduled task
#   cleanup               - remove bootstrap files (keep site + task)
import argparse
import json
import os
import secrets
import sys
import time

import requests

USERNAME = "gillhopitalsoftware1"
DOMAIN = USERNAME + ".pythonanywhere.com"
V0 = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}"
WEBSITES = f"https://www.pythonanywhere.com/api/v1/user/{USERNAME}/websites/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "pa_token.txt")
STATE_FILE = os.path.join(BASE_DIR, "pa_state.json")
LOCAL_ENV = os.path.join(BASE_DIR, ".env")
LOCAL_DB = os.path.join(BASE_DIR, "ghos_dev.db")

WSGI_REMOTE = f"/var/www/{USERNAME}_pythonanywhere_com_wsgi.py"
SETUP_REMOTE = f"/home/{USERNAME}/setup.sh"
ENV_REMOTE = f"/home/{USERNAME}/pa_env.txt"
LOG_REMOTE = f"/home/{USERNAME}/pa_setup.log"
REMOTE_DB = f"/home/{USERNAME}/gil-clinic/ghos_prod.db"
REMOTE_ENV = f"/home/{USERNAME}/gil-clinic/.env"
REMOTE_CREDS = f"/home/{USERNAME}/gil-clinic/admin_credentials.txt"


def hdrs():
    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    return {"Authorization": f"Token {token}"}


def state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(s: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)


def get_secret() -> str:
    s = state()
    if "secret" not in s:
        s["secret"] = secrets.token_hex(24)
        save_state(s)
    return s["secret"]


def gen_passwords() -> dict:
    s = state()
    if "passwords" not in s:
        s["passwords"] = {
            "SUPER_ADMIN_PASSWORD": "GilClinic#" + secrets.token_hex(6) + "!",
            "CEO_PASSWORD": "GilClinic#" + secrets.token_hex(6) + "!",
        }
        save_state(s)
    return s["passwords"]


def api(method: str, url: str, **kw):
    r = requests.request(method, url, headers=hdrs(), timeout=60, **kw)
    return r


def cmd_status(_):
    cpu = api("GET", V0 + "/cpu/")
    print("CPU:", cpu.json() if cpu.ok else cpu.text)
    wa = api("GET", V0 + "/webapps/")
    print("WEBAPPS:", wa.status_code, (wa.json() if wa.ok else wa.text))
    ws = api("GET", WEBSITES)
    print("WEBSITES:", ws.status_code, (ws.json() if ws.ok else ws.text))
    sc = api("GET", V0 + "/schedule/")
    print("SCHEDULE:", sc.status_code, (sc.json() if sc.ok else sc.text))
    tree = api("GET", V0 + "/files/tree/?path=/home/%s/" % USERNAME)
    print("HOME TREE:", tree.status_code, (tree.json() if tree.ok else tree.text[:300]))


def _put(remote_path: str, content: bytes, desc: str):
    r = api("POST", V0 + "/files/path" + remote_path, files={"content": content})
    print(f"UPLOAD {desc}: {r.status_code}", ("" if r.ok else r.text[:300]))
    return r.ok


def cmd_bootstrap(_):
    # 1) setup.sh
    setup = """#!/bin/bash
exec >>/home/{u}/pa_setup.log 2>&1
echo "=== SETUP START $(date -u) ==="
cd /home/{u} || {{ echo CD_HOME_FAIL; exit 1; }}
if [ ! -d gil-clinic/.git ]; then
  git clone https://github.com/gurjeetsinghgill8-web/gil-clinic.git || {{ echo CLONE_FAIL; exit 1; }}
else
  (cd gil-clinic && git pull) || true
fi
cd /home/{u}/gil-clinic || {{ echo CD_APP_FAIL; exit 1; }}
echo "--- disk before ---"; du -sh /home/{u} 2>/dev/null; du -sh /home/{u}/.cache/pip 2>/dev/null
echo "--- cleanup old venv + pip cache ---"
rm -rf /home/{u}/.virtualenvs/gilclinic
rm -rf /home/{u}/.cache/pip
VENV=/home/{u}/.virtualenvs/gilclinic
for PY in python3.12 python3.11 python3.10 python3; do
  if command -v $PY >/dev/null 2>&1; then
    echo "venv from $PY"
    $PY -m venv "$VENV" && break
  fi
done
[ -x "$VENV/bin/python" ] || {{ echo VENV_FAIL; exit 1; }}
"$VENV/bin/pip" install --upgrade pip -q || {{ echo PIPUP_FAIL; exit 1; }}
"$VENV/bin/pip" install --no-cache-dir -r pa_requirements.txt || {{ echo PIP_FAIL; exit 1; }}
echo "--- disk after ---"; du -sh /home/{u} 2>/dev/null
if [ -f /home/{u}/pa_env.txt ]; then
  cp /home/{u}/pa_env.txt .env
  echo ENV_COPIED
fi
echo "=== SETUP_DONE $(date -u) ==="
""".format(u=USERNAME)
    _put(SETUP_REMOTE, setup.encode(), "setup.sh")

    # 2) .env content
    groq = ""
    if os.path.exists(LOCAL_ENV):
        with open(LOCAL_ENV, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    groq = line.split("=", 1)[1].strip()
                    break
    p = gen_passwords()
    env = (
        f"GROQ_API_KEY={groq}\n"
        f"APP_BASE_URL=https://{DOMAIN}\n"
        f"GHOS_DB_URL=sqlite:////home/{USERNAME}/gil-clinic/ghos_prod.db\n"
        f"GHOS_DB_URL_ASYNC=sqlite+aiosqlite:////home/{USERNAME}/gil-clinic/ghos_prod.db\n"
        f"SUPER_ADMIN_PASSWORD={p['SUPER_ADMIN_PASSWORD']}\n"
        f"CEO_PASSWORD={p['CEO_PASSWORD']}\n"
        f"SECRET_KEY={secrets.token_hex(32)}\n"
        f"GHOS_AI_KEYS_SECRET={secrets.token_hex(32)}\n"
        "SYSTEM_AI_FALLBACK_ENABLED=false\n"
    )
    _put(ENV_REMOTE, env.encode(), "pa_env.txt (.env)")

    # 3) bootstrap WSGI (gate with random secret, runs setup.sh in background)
    wsgi = """import subprocess

SECRET = "{secret}"

def application(environ, start_response):
    path = environ.get("PATH_INFO", "")
    qs = environ.get("QUERY_STRING", "")
    if path == "/__setup__" and ("key=" + SECRET) in qs:
        with open("/home/{u}/pa_setup.log", "ab") as f:
            subprocess.Popen(
                ["bash", "/home/{u}/setup.sh"],
                stdout=f, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"STARTED\\n"]
    start_response("403 Forbidden", [("Content-Type", "text/plain")])
    return [b"forbidden\\n"]
""".format(secret=get_secret(), u=USERNAME)
    _put(WSGI_REMOTE, wsgi.encode(), "bootstrap WSGI")
    print("Bootstrap upload done.")


def cmd_webapp_create(_):
    r = api("POST", V0 + "/webapps/",
            data={"domain_name": DOMAIN, "python_version": "python310"})
    print("WEBAPP CREATE:", r.status_code, r.text[:300])
    if not r.ok and r.status_code != 409:
        return
    r2 = api("PATCH", V0 + f"/webapps/{DOMAIN}/",
             data={"source_directory": f"/home/{USERNAME}"})
    print("WEBAPP PATCH:", r2.status_code, r2.text[:300])
    r3 = api("POST", V0 + f"/webapps/{DOMAIN}/reload/")
    print("WEBAPP RELOAD:", r3.status_code, r3.text[:200])


def cmd_trigger(_):
    url = f"https://{DOMAIN}/__setup__?key={get_secret()}"
    print("TRIGGER:", url)
    try:
        r = requests.get(url, timeout=20)
        print("RESULT:", r.status_code, r.text[:200])
    except Exception as e:
        print("TRIGGER FAIL:", e)


def cmd_log(_):
    r = api("GET", V0 + "/files/path" + LOG_REMOTE)
    if r.ok:
        text = r.content.decode("utf-8", "replace")
        lines = text.strip().splitlines()
        out = "\n".join(lines[-40:]).encode("ascii", "replace").decode()
        print(out)
        print("--- (log lines:", len(lines), ")")
    else:
        print("LOG READ FAIL:", r.status_code, r.text[:300])


def cmd_webapp_reload(_):
    r = api("POST", V0 + f"/webapps/{DOMAIN}/reload/")
    print("WEBAPP RELOAD:", r.status_code, r.text[:200])


def cmd_webapp_delete(_):
    r = api("DELETE", V0 + f"/webapps/{DOMAIN}/")
    print("WEBAPP DELETE:", r.status_code, r.text[:200])


def cmd_site_create(_):
    command = (
        f"/home/{USERNAME}/.virtualenvs/gilclinic/bin/uvicorn "
        f"--app-dir /home/{USERNAME}/gil-clinic --uds ${{DOMAIN_SOCKET}} main_v2:app"
    )
    r = api("POST", WEBSITES, json={
        "domain_name": DOMAIN,
        "enabled": True,
        "webapp": {"command": command},
    })
    print("SITE CREATE:", r.status_code, r.text[:400])


def cmd_site_get(_):
    r = api("GET", WEBSITES + DOMAIN + "/")
    print("SITE GET:", r.status_code, (r.json() if r.ok else r.text[:300]))


def cmd_site_reload(_):
    r = api("POST", WEBSITES + DOMAIN + "/reload/")
    print("SITE RELOAD:", r.status_code, r.text[:300])


def cmd_upload_db(_):
    if not os.path.exists(LOCAL_DB):
        print("local DB not found:", LOCAL_DB)
        return
    with open(LOCAL_DB, "rb") as f:
        data = f.read()
    r = api("POST", V0 + "/files/path" + REMOTE_DB, files={"content": data})
    print("DB UPLOAD:", r.status_code, len(data), "bytes", ("" if r.ok else r.text[:300]))


def cmd_backup_task(_):
    r = api("POST", V0 + "/schedule/", json={
        "command": f"python /home/{USERNAME}/gil-clinic/backup_now.py",
        "enabled": True,
        "interval": "daily",
        "hour": 23,
        "minute": 30,
    })
    print("BACKUP TASK:", r.status_code, (r.json() if r.ok else r.text[:300]))


def cmd_cleanup(_):
    for p in (SETUP_REMOTE, ENV_REMOTE):
        r = api("DELETE", V0 + "/files/path" + p)
        print("DEL", p, r.status_code)
    # leave a harmless default WSGI file behind
    default_wsgi = b'# default placeholder\ndef application(environ, start_response):\n    start_response("200 OK", [("Content-Type", "text/plain")])\n    return [b"GIL CLINIC placeholder\\n"]\n'
    _put(WSGI_REMOTE, default_wsgi, "wsgi placeholder")
    r = api("DELETE", V0 + "/files/path" + LOG_REMOTE)
    print("DEL log:", r.status_code)


def cmd_creds(_):
    r = api("GET", V0 + "/files/path" + REMOTE_CREDS)
    print("CREDS FILE:", r.status_code)
    if r.ok:
        print(r.content.decode("utf-8", "replace"))


def cmd_env_check(_):
    r = api("GET", V0 + "/files/path" + REMOTE_ENV)
    print("REMOTE .env:", r.status_code)
    if r.ok:
        print(r.content.decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=[
        "status", "bootstrap", "webapp_create", "webapp_reload", "trigger", "log",
        "webapp_delete", "site_create", "site_get", "site_reload",
        "upload_db", "backup_task", "cleanup", "creds", "env_check",
    ])
    args = ap.parse_args()
    fn = {
        "status": cmd_status, "bootstrap": cmd_bootstrap,
        "webapp_create": cmd_webapp_create, "webapp_reload": cmd_webapp_reload,
        "trigger": cmd_trigger,
        "log": cmd_log, "webapp_delete": cmd_webapp_delete,
        "site_create": cmd_site_create, "site_get": cmd_site_get,
        "site_reload": cmd_site_reload, "upload_db": cmd_upload_db,
        "backup_task": cmd_backup_task, "cleanup": cmd_cleanup,
        "creds": cmd_creds, "env_check": cmd_env_check,
    }[args.cmd]
    fn(args)


if __name__ == "__main__":
    main()
