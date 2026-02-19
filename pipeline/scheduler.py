import threading
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline.utils import DATA_DIR, today_date_str

_scheduler = None
_lock = threading.Lock()


def _pipeline_already_ran_today() -> bool:
    digest_path = DATA_DIR / "digests" / today_date_str() / "digest.json"
    return digest_path.exists()


def _run_pipeline():
    if _pipeline_already_ran_today():
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
