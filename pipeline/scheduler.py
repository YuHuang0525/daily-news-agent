import threading
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline.utils import DATA_DIR, today_date_str, load_sources, slugify, cleanup_old_data

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


def _run_pipeline():
    # Clean up old data first to free disk/memory before the new run
    try:
        cleanup_old_data(max_age_days=7)
    except Exception as e:
        print(f"[scheduler] Cleanup error (non-fatal): {e}")

    if _pipeline_already_ran_today():
        missing = _sources_missing_raw_data()
        if missing:
            print(f"[scheduler] Digest exists but sources missing data: {missing} — retrying...")
            try:
                from pipeline.run_daily import run_retry_sources
                run_retry_sources(missing)
                print(f"[scheduler] Retry complete for: {missing}")
            except Exception as e:
                print(f"[scheduler] Retry error: {e}")
        else:
            print("[scheduler] Today's digest already exists — skipping.")
        return
    try:
        print("[scheduler] Starting daily pipeline...")
        from pipeline.run_daily import run
        run()
        print("[scheduler] Daily pipeline complete.")
    except Exception as e:
        print(f"[scheduler] Pipeline error: {e}")


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
        )
        _scheduler.start()
        print("[scheduler] Started — pipeline running now, then daily at 15:00 UTC (7:00 AM PST)")
