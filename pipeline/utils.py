import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def load_sources():
    config_path = ROOT_DIR / "config" / "sources.yml"
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def load_preferences():
    config_path = ROOT_DIR / "config" / "preferences.json"
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _default_timezone_name() -> str:
    # Env override for cron / servers that run in UTC
    tz = os.getenv("PIPELINE_TIMEZONE")
    if tz:
        return tz
    try:
        prefs = load_preferences()
        tz = prefs.get("timezone")
        if tz:
            return tz
    except Exception:
        pass
    # Project default (PST/PDT)
    return "America/Los_Angeles"


def now_in_timezone(tz_name: str | None = None) -> datetime:
    tz_name = tz_name or _default_timezone_name()
    try:
        from zoneinfo import ZoneInfo  # py3.9+

        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        # Fallback to local time if zoneinfo isn't available for some reason
        return datetime.now()


def today_date_str(tz_name: str | None = None) -> str:
    return now_in_timezone(tz_name).strftime("%Y-%m-%d")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text[:60].strip("-") or "item"


def cleanup_old_data(max_age_days: int = 7) -> int:
    """Remove date-stamped data directories older than *max_age_days*.

    Scans data/raw, data/processed, data/digests, and data/articles for
    subdirectories named YYYY-MM-DD and deletes those older than the
    cutoff.  Non-date directories and special files (latest.json, etc.)
    are left untouched.
    """
    cutoff = now_in_timezone().date() - timedelta(days=max_age_days)
    dirs_to_scan = [
        DATA_DIR / "raw",
        DATA_DIR / "processed",
        DATA_DIR / "digests",
        DATA_DIR / "articles",
    ]
    removed = 0
    for parent in dirs_to_scan:
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            try:
                folder_date = datetime.strptime(child.name, "%Y-%m-%d").date()
            except ValueError:
                continue  # not a date folder
            if folder_date < cutoff:
                shutil.rmtree(child)
                removed += 1
    if removed:
        print(f"[cleanup] Removed {removed} data folder(s) older than {max_age_days} days")
    else:
        print(f"[cleanup] No data folders older than {max_age_days} days")
    return removed


def current_rss_mb() -> float | None:
    """Return current process RSS in MB on Linux, otherwise None."""
    status_path = Path("/proc/self/status")
    if not status_path.exists():
        return None
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) / 1024
    except Exception:
        return None
    return None


def compact_runtime_memory(label: str = "runtime") -> None:
    """Force Python GC and ask glibc to return free heap pages to the OS."""
    import gc

    before = current_rss_mb()
    collected = gc.collect()
    trim_result = None

    if os.name == "posix":
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            trim_result = libc.malloc_trim(0)
        except Exception:
            trim_result = None

    after = current_rss_mb()
    if before is not None and after is not None:
        print(
            f"[memory] {label}: rss {before:.1f} MB -> {after:.1f} MB; "
            f"gc_collected={collected}; malloc_trim={trim_result}"
        )
    else:
        print(
            f"[memory] {label}: gc_collected={collected}; "
            f"malloc_trim={trim_result}; rss=unavailable"
        )
