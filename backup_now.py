"""backup_now.py — one-click safe backup of GIL CLINIC data files.

Usage:
    python backup_now.py                    # backup to backups/ folder
    python backup_now.py "D:\\OneDrive\\GIL_BACKUPS"   # + mirror copy

- Copies all database files to backups/YYYY-MM-DD_HHMMSS/
- Keeps the last 30 local backups (older ones are pruned)
- Optional mirror folder (OneDrive / Google Drive / pen drive) for extra safety
- Safe to run any time — even while the server is running
"""

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP_ROOT = ROOT / "backups"
DB_FILES = ["ghos_dev.db", "ghos_prod.db", "cardioqueue.db", "test_ghos.db"]


def main() -> int:
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    dest = BACKUP_ROOT / stamp
    dest.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in DB_FILES:
        src = ROOT / name
        if src.exists() and src.stat().st_size > 0:
            shutil.copy2(src, dest / name)
            copied.append(name)

    if not copied:
        print("[WARN] No database files found to back up.")
    else:
        print(f"[OK] Backup: {len(copied)} file(s) -> {dest}")

    # Optional mirror (OneDrive / Google Drive / pen drive)
    mirror = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if mirror:
        try:
            m = Path(mirror)
            m.mkdir(parents=True, exist_ok=True)
            for name in copied:
                shutil.copy2(ROOT / name, m / name)
            print(f"[OK] Mirror copy to {m}")
        except Exception as e:
            print(f"[WARN] Mirror copy failed: {e}")

    # Prune old backups (keep last 30)
    try:
        dirs = sorted([d for d in BACKUP_ROOT.iterdir() if d.is_dir()], reverse=True)
        for old in dirs[30:]:
            shutil.rmtree(old, ignore_errors=True)
            print(f"[OK] Pruned old backup: {old.name}")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
