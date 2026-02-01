import json
import os
import re
from datetime import datetime
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
