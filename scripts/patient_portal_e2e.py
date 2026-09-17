"""Patient Portal — one-command real-browser E2E (Smart OPD).

Kya karta hai:
  1. ek test SQLite DB banata hai (`test_patient_portal_ui.db`)
  2. usko seed karta hai (test patient)
  3. app ko local port par chalata hai (uvicorn, background)
  4. `scripts/patient_portal_e2e.cjs` (Playwright) chalata hai —
     doctor login → patient link → patient portal (verify → readings → graphs)
     → "Doctor ko bhejo" read-only link → Patient Monitor tab
  5. server band karta hai aur exit code wapas deta hai

Run:  python scripts/patient_portal_e2e.py
Zaroorat: playwright (`cd . && npm i` pehle se ho) + `pip install -r requirements.txt`
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_FILE = ROOT / "test_patient_portal_ui.db"
PORT = 8099
BASE = f"http://127.0.0.1:{PORT}"


def _wait_for_port(host: str, port: int, timeout: float = 40.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    env = dict(os.environ)
    env["GHOS_DB_URL"] = f"sqlite:///{DB_FILE}"
    env["PYTHONIOENCODING"] = "utf-8"
    if DB_FILE.exists():
        try:
            DB_FILE.unlink()
        except OSError:
            pass

    print(f"[e2e] DB: {DB_FILE}")
    print("[e2e] app start ho raha hai…")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main_v2:app", "--host", "127.0.0.1", "--port", str(PORT),
         "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
    )
    try:
        if not _wait_for_port("127.0.0.1", PORT):
            print("[e2e] app start nahi hua", file=sys.stderr)
            return 1
        print(f"[e2e] app ready → {BASE}")

        print("[e2e] seed…")
        seed = subprocess.run([sys.executable, str(ROOT / "scripts" / "patient_portal_seed.py")],
                              cwd=str(ROOT), env=env)
        if seed.returncode != 0:
            print("[e2e] seed fail", file=sys.stderr)
            return 1

        print("[e2e] browser test chal raha hai…\n")
        result = subprocess.run(["node", str(ROOT / "scripts" / "patient_portal_e2e.cjs")],
                                cwd=str(ROOT), env=env)
        print(f"\n[e2e] browser test exit code: {result.returncode}")
        return result.returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print("[e2e] server band ho gaya")


if __name__ == "__main__":
    raise SystemExit(main())
