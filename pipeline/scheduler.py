import os
import shlex
import subprocess
import sys
import threading
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pipeline.utils import (
    DATA_DIR,
    compact_runtime_memory,
    cleanup_old_data,
    load_sources,
    slugify,
    today_date_str,
)

_scheduler = None
_lock = threading.Lock()


def _pipeline_already_ran_today() -> bool:
    digest_path = DATA_DIR / "digests" / today_date_str() / "digest.json"
    return digest_path.exists()


def _sources_missing_raw_data() -> list[str]:
    """Return names of enabled sources that have no raw data for today."""
    date_str = today_date_str()
    raw_dir = DATA_DIR / "raw" / date_str
    missing = []
    for s in load_sources():
        if not s.get("enabled"):
            continue
        name = s.get("name", "")
        raw_file = raw_dir / f"{slugify(name)}.json"
        if not raw_file.exists():
            missing.append(name)
        else:
            # Also treat empty files / empty arrays as missing
            try:
                import json
                data = json.loads(raw_file.read_text(encoding="utf-8"))
                if not data:
                    missing.append(name)
            except Exception:
                missing.append(name)
    return missing


def _data_retention_days() -> int:
    try:
        return max(0, int(os.getenv("DATA_RETENTION_DAYS", "7")))
    except ValueError:
        return 7


def _maintenance_interval_hours() -> int:
    try:
        return max(0, int(os.getenv("MAINTENANCE_INTERVAL_HOURS", "6")))
    except ValueError:
        return 6


def _run_pipeline_subprocess(retry_sources: list[str] | None = None) -> None:
    command = [sys.executable, "-m", "pipeline.run_daily"]
    for source_name in retry_sources or []:
        command.extend(["--retry-source", source_name])

    printable_command = " ".join(shlex.quote(part) for part in command)
    print(f"[scheduler] Launching pipeline subprocess: {printable_command}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(command, cwd=str(DATA_DIR.parent), env=env)
    if result.returncode != 0:
        raise RuntimeError(f"pipeline subprocess exited with code {result.returncode}")


def _run_maintenance():
    try:
        cleanup_old_data(max_age_days=_data_retention_days())
    except Exception as e:
        print(f"[scheduler] Cleanup error (non-fatal): {e}")
    finally:
        compact_runtime_memory("scheduler maintenance")


def _run_pipeline():
    # Clean up old data first; the pipeline itself runs out-of-process so its
    # heap is returned to the OS when the child exits.
    try:
        cleanup_old_data(max_age_days=_data_retention_days())
    except Exception as e:
        print(f"[scheduler] Cleanup error (non-fatal): {e}")

    try:
        if _pipeline_already_ran_today():
            missing = _sources_missing_raw_data()
            if missing:
                print(f"[scheduler] Digest exists but sources missing data: {missing} - retrying...")
                try:
                    _run_pipeline_subprocess(retry_sources=missing)
                    print(f"[scheduler] Retry complete for: {missing}")
                except Exception as e:
                    print(f"[scheduler] Retry error: {e}")
            else:
                print("[scheduler] Today's digest already exists - skipping.")
            return

        print("[scheduler] Starting daily pipeline...")
        _run_pipeline_subprocess()
        print("[scheduler] Daily pipeline complete.")
    except Exception as e:
        print(f"[scheduler] Pipeline error: {e}")
    finally:
        compact_runtime_memory("scheduler after pipeline")


def start_scheduler():
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return

        _scheduler = BackgroundScheduler(timezone=pytz.utc)

        # 7:00 AM PST = 15:00 UTC
        # During PDT (summer) this becomes 8:00 AM — adjust to 14:00 if you want strict 7 AM year-round
        _scheduler.add_job(
            _run_pipeline,
            CronTrigger(hour=15, minute=0, timezone=pytz.utc),
            id="daily_pipeline",
            replace_existing=True,
            next_run_time=datetime.now(pytz.utc),  # also run immediately on startup
            max_instances=1,
            coalesce=True,
        )
        maintenance_hours = _maintenance_interval_hours()
        if maintenance_hours > 0:
            _scheduler.add_job(
                _run_maintenance,
                IntervalTrigger(hours=maintenance_hours, timezone=pytz.utc),
                id="runtime_maintenance",
                replace_existing=True,
                next_run_time=datetime.now(pytz.utc) + timedelta(minutes=30),
                max_instances=1,
                coalesce=True,
            )
        _scheduler.start()
        print(
            "[scheduler] Started - pipeline running now, then daily at 15:00 UTC "
            "(8:00 AM PDT / 7:00 AM PST)"
        )
