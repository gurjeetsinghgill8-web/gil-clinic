"""In-app automatic backups — for hosted environments without cron.

PythonAnywhere free has NO scheduled tasks, and the Oracle deploy uses
systemd/cron. To make every deployment safe by default, this module:

  1. Takes a backup at every app startup (before anything writes data)
  2. Schedules a daily backup at 23:30 UTC via APScheduler (runs inside
     the web app process — the site is always up)

Backups go to <project>/backups/YYYY-MM-DD_HHMMSS/, keeping the last 30.
"""
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_scheduler = None


def _project_root() -> Path:
    # src/infrastructure/clinic/services/auto_backup.py -> project root
    return Path(__file__).resolve().parents[4]


def backup_now() -> None:
    try:
        root = _project_root()
        src = root / "ghos_prod.db"
        if not (src.exists() and src.stat().st_size > 0):
            src = root / "ghos_dev.db"
        if not (src.exists() and src.stat().st_size > 0):
            logger.info("Auto-backup skipped: no database file yet")
            return
        dest_dir = root / "backups" / time.strftime("%Y-%m-%d_%H%M%S")
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / src.name)
        # prune: keep last 30
        backups_root = root / "backups"
        dirs = sorted([d for d in backups_root.iterdir() if d.is_dir()], reverse=True)
        for old in dirs[30:]:
            shutil.rmtree(old, ignore_errors=True)
        logger.info("Auto-backup saved: %s", dest_dir.name)
    except Exception as exc:  # backup must never take the app down
        logger.warning("Auto-backup failed: %s", exc)


def start_auto_backup() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    backup_now()  # startup backup
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(backup_now, "cron", hour=23, minute=30, id="gilclinic_auto_backup")
        _scheduler.start()
        logger.info("Auto-backup daily job scheduled (23:30 UTC)")
    except Exception as exc:
        logger.warning("Auto-backup scheduler failed (startup backup still taken): %s", exc)


def stop_auto_backup() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
