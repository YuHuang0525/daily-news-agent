import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from pipeline.fetch import fetch_source, save_raw_items
from pipeline.process import (
    build_digest,
    deduplicate,
    enrich_items,
    normalize_item,
    render_digest_markdown,
    save_digest,
    save_digest_markdown,
    save_processed,
)
from pipeline.utils import (
    DATA_DIR,
    ensure_dir,
    load_preferences,
    load_sources,
    today_date_str,
)


def run():
    load_dotenv()
    sources = [s for s in load_sources() if s.get("enabled")]
    prefs = load_preferences()
    date_str = today_date_str()

    raw_dir = DATA_DIR / "raw" / date_str
    processed_dir = DATA_DIR / "processed" / date_str
    digest_dir = DATA_DIR / "digests" / date_str
    latest_path = DATA_DIR / "digests" / "latest.json"

    ensure_dir(raw_dir)
    ensure_dir(processed_dir)
    ensure_dir(digest_dir)

    all_items = []
    for source in sources:
        print(f"📰 Fetching {source['name']}...")
        try:
            items = fetch_source(source)
            if items:
                save_raw_items(raw_dir, source["name"], items)
                for item in items:
                    all_items.append(normalize_item(source, item))
                print(f"✅ {source['name']}: {len(items)} items")
            else:
                print(f"⚠️  {source['name']}: No items found")
        except Exception as e:
            print(f"❌ Failed to fetch {source['name']}: {e}")
            continue

    all_items = deduplicate(all_items)
    enriched = enrich_items(all_items, prefs.get("low_credibility_threshold", 50))
    save_processed(processed_dir, enriched)  # This now saves with timestamp wrapper
    digest = build_digest(enriched, prefs.get("daily_digest_items", 12))
    save_digest(digest_dir, digest, latest_path)
    markdown = render_digest_markdown(digest)
    save_digest_markdown(digest_dir, markdown)

    with (DATA_DIR / "digests" / "latest.meta.json").open("w", encoding="utf-8") as f:
        json.dump(
            {"date": date_str, "count": len(enriched)}, f, ensure_ascii=False, indent=2
        )


if __name__ == "__main__":
    run()
