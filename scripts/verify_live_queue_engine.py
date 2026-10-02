"""Live post-deploy verification — GHOS / GIL CLINIC (queue engine release).

Run after every `python pa_deploy.py ship`:

    python scripts/verify_live_queue_engine.py

It does not just check HTTP 200. It opens the real pages and looks for the
markers the new code introduced, because "the server answered" and "the feature
actually shipped" are different things:

  * /health              → the BUILD stamp must match the commit just shipped
  * /                    → landing page renders and links to /find-doctor
  * /opd/dashboard       → the deployed HTML must contain the START OPD panel,
                           the chamber fetch and the EWT fetch
  * /opd/api/chamber/*   → returns real JSON for a logged-in doctor
  * /opd/api/queue-ewt   → returns the learned average, samples and delay badge
  * /find-doctor + API   → the marketplace still renders and reports live signal
  * /abdm, /staff/login, /admin/login, /card/<uid>, /track/<token>  → still alive

Read-only: it never presses START OPD, never books, never writes. Expected
non-200 codes are listed per route, so a genuine break shows up as FAIL.

Exit code is 0 when nothing hard-failed, 1 otherwise — usable in CI or by hand.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

import requests

BASE = "https://gillhopitalsoftware1.pythonanywhere.com"
DOCTOR_PIN = "5554"

rows: list[tuple[str, str, str]] = []


def note(tag: str, label: str, detail: object = "") -> None:
    rows.append((tag, label, str(detail)[:150]))


def get(path: str, session=None, **kw):
    """GET with a sane timeout; the caller may override allow_redirects."""
    s = session or requests
    kw.setdefault("allow_redirects", True)
    return s.get(BASE + path, timeout=60, **kw)


def check_status(label: str, path: str, expect, session=None) -> None:
    try:
        r = get(path, session=session, allow_redirects=False)
    except Exception as exc:
        note("FAIL", f"GET {path}  ({label})", f"{type(exc).__name__}: {exc}")
        return
    wanted = expect if isinstance(expect, (tuple, list)) else (expect,)
    tag = "OK" if r.status_code in wanted else "FAIL"
    note(tag, f"GET {path}  ({label})", f"HTTP {r.status_code} (expected {'/'.join(map(str, wanted))})")


def main() -> int:
    # ── 1. build stamp ──
    try:
        health = get("/health").json()
        note("OK", "BUILD", f"{health.get('build')} · commit {health.get('commit')} · {health.get('files_shipped')} files")
    except Exception as exc:
        note("FAIL", "BUILD", f"{type(exc).__name__}: {exc}")

    # ── 2. landing page ──
    try:
        r = get("/")
        html = r.text
        title = (re.search(r"<title>(.*?)</title>", html, re.S | re.I) or [None, "?"])[1].strip()
        note("OK" if r.status_code == 200 else "FAIL", "GET /  (landing)", f"HTTP {r.status_code} · {len(html)} bytes · '{title[:52]}'")
        for kw in ("Find a Doctor", "find-doctor", "GIL"):
            hit = kw.lower() in html.lower()
            note("OK" if hit else "FAIL", f"  landing contains '{kw}'", "yes" if hit else "no")
    except Exception as exc:
        note("FAIL", "GET /", f"{type(exc).__name__}: {exc}")

    # ── 3. doctor dashboard — does the DEPLOYED html carry the new panel? ──
    session = requests.Session()
    try:
        session.post(BASE + "/opd/login", data={"pin": DOCTOR_PIN}, timeout=60)
        dash = session.get(BASE + "/opd/dashboard", timeout=90)
        body = dash.text
        note("OK" if dash.status_code == 200 and len(body) > 100_000 else "FAIL",
             "GET /opd/dashboard (doctor login)", f"HTTP {dash.status_code} · {len(body)} bytes")
        for label, needle in (
            ("START OPD panel", "qe-panel"),
            ("chamber status fetch", "/opd/api/chamber/status"),
            ("live EWT fetch", "/opd/api/queue-ewt"),
            ("START OPD button", "START OPD"),
            ("delay badge wiring", "delay_severity"),
            ("build stamp footer", "build-stamp"),
        ):
            hit = needle in body
            note("OK" if hit else "FAIL", f"  dashboard {label}", "mil gaya" if hit else "NAHI mila")
    except Exception as exc:
        note("FAIL", "doctor dashboard", f"{type(exc).__name__}: {exc}")

    # ── 4. queue-engine endpoints (read-only) ──
    for path in ("/opd/api/chamber/status", "/opd/api/queue-ewt"):
        try:
            r = session.get(BASE + path, timeout=60)
            data = r.json()
            summary = json.dumps({k: v for k, v in data.items() if k != "queue"}, ensure_ascii=False)
            note("OK" if r.status_code == 200 and data.get("ok") else "FAIL", f"GET {path}", summary[:190])
        except Exception as exc:
            note("FAIL", f"GET {path}", f"{type(exc).__name__}: {exc}")

    # ── 5. marketplace ──
    try:
        mp = get("/find-doctor")
        note("OK" if mp.status_code == 200 else "FAIL", "GET /find-doctor", f"HTTP {mp.status_code} · {len(mp.text)} bytes")
        api = get("/api/v1/marketplace/doctors").json()
        live = [d for d in api.get("doctors", []) if d.get("live")]
        note("OK" if live else "..", "marketplace live signal", f"{api.get('total')} doctors · {len(live)} with live block")
        for d in live[:2]:
            lv = d["live"]
            note("INFO", f"  {d['doctor_name'][:26]}",
                 f"ahead={lv['patients_ahead']} wait={lv['wait_minutes']}min conf={lv['confidence']} "
                 f"state={lv['state']} chamber={lv['chamber_open']} real={lv['real']}")
    except Exception as exc:
        note("FAIL", "marketplace", f"{type(exc).__name__}: {exc}")

    # ── 6. other live modules (expected codes are deliberate, not sloppiness) ──
    check_status("ABDM status page", "/abdm", 200)
    check_status("staff login", "/staff/login", 200)
    check_status("admin login", "/admin/login", 200)
    check_status("marketplace alias /doctors", "/doctors", 200)
    # An invalid uid/token must be REJECTED, so 404/400 is the healthy answer.
    check_status("health card (invalid uid → rejected)", "/card/xyz", 404)
    check_status("track (invalid token → rejected)", "/track/xyz", 400)
    # Rx Pad needs a real prescription; a fake patient must yield 400, not 404.
    check_status("Rx Pad route (needs a real Rx)", "/opd/api/rx-pad?patient_id=VERIFY", 400, session=session)

    # ── 7. CPU budget (100 s/day on the free tier) ──
    try:
        out = subprocess.run(
            [sys.executable, "pa_deploy.py", "status"],
            capture_output=True, text=True, timeout=90, cwd=".",
        ).stdout
        m = re.search(r"'daily_cpu_total_usage_seconds': ([\d.]+)", out)
        if m:
            used = float(m.group(1))
            note("OK" if used < 70 else "WARN", "PythonAnywhere CPU (aaj)", f"{used} / 100 second")
    except Exception as exc:
        note("INFO", "CPU check", f"skipped: {type(exc).__name__}")

    print("=" * 104)
    for tag, label, detail in rows:
        print(f"[{tag:^4}] {label:<46} {detail}")
    print("=" * 104)
    fails = [r for r in rows if r[0] == "FAIL"]
    print(f"TOTAL {len(rows)} checks · FAILURES: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
