#!/usr/bin/env python3
"""GIL CLINIC — Cloudflare quick tunnel helper (patients ke liye public link).

START_TUNNEL.bat se chalein (server pehle START_LOCAL.bat se chalu ho).
Ye script:
  1. cloudflared quick tunnel chalu karta hai (localhost:8000)
  2. trycloudflare.com URL pakad leta hai
  3. .env mein APP_BASE_URL update kar deta hai — server restart ki zaroorat NAHI
     (app har request par .env dobara padhta hai)
  4. URL screen par dikhata hai

Note: quick tunnel ka URL har baar badalta hai — isliye har start par .env
auto-update hota hai. Permanent URL ke liye: Oracle VM (public IP stable) ya
domain + named tunnel (CLOUD_DEPLOY_GUIDE.md Part 3).
"""
import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED = os.path.join(BASE_DIR, "cloudflared.exe")
ENV_FILE = os.path.join(BASE_DIR, ".env")

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def update_env(url: str) -> bool:
    """APP_BASE_URL ko .env mein update karo (missing ho to append)."""
    if not os.path.exists(ENV_FILE):
        print("[WARN] .env nahi mila — APP_BASE_URL update skip.")
        return False
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_line = f"APP_BASE_URL={url}\n"
    replaced = False
    out = []
    for line in lines:
        if line.startswith("APP_BASE_URL="):
            out.append(new_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append("\n# Public URL for patient tracking links (auto-set by start_tunnel.py)\n")
        out.append(new_line)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(out)
    return True


def main() -> int:
    if not os.path.exists(CLOUDFLARED):
        print("[ERROR] cloudflared.exe nahi mila. CLOUD_DEPLOY_GUIDE.md Part 3 dekhein.")
        return 1

    print("=" * 58)
    print("  GIL CLINIC - Patient Link Tunnel (Cloudflare)")
    print("=" * 58)
    print("  Tunnel chalu ho raha hai... URL milne par .env update hoga.")
    print("  (Server pehle se chalu hona chahiye — START_LOCAL.bat)")
    print()

    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    url = None
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if url is None:
                m = URL_RE.search(line)
                if m:
                    url = m.group(0)
                    if update_env(url):
                        print()
                        print(f"  [OK] APP_BASE_URL set: {url}")
                        print("       Server restart ki zaroorat NAHI — agla patient message")
                        print("       isi public link ke saath jayega.")
                        print()
                        print(f"  PATIENT LINK: {url}")
                        print()
                        print("  Ye window BAND mat karna — link isi se chalta hai.")
                        print("  Ctrl+C se band karein.")
    except KeyboardInterrupt:
        print()
        print("  Tunnel band ho raha hai...")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
