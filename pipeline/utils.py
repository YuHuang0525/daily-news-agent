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


def today_date_str():
    return datetime.now().strftime("%Y-%m-%d")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text[:60].strip("-") or "item"
