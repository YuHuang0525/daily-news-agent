import json
import sys
import os
import asyncio
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
    enrich_items_async,
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


async def _fetch_one_source(source, sem: asyncio.Semaphore):
    async with sem:
        items = await asyncio.to_thread(fetch_source, source)
        return source, items or []


async def run_async():
    load_dotenv()
    sources = [s for s in load_sources() if s.get("enabled")]
    prefs = load_preferences()
    tz_name = os.getenv("PIPELINE_TIMEZONE", prefs.get("timezone", "America/Los_Angeles"))
    date_str = today_date_str(tz_name)
    for s in sources:
        # Pass pipeline timezone through to fetchers (e.g., STAT day page logic)
        s["_tz_name"] = tz_name

    max_concurrency = int(
        os.getenv("PIPELINE_MAX_CONCURRENCY", prefs.get("max_concurrency", 3))
    )
    max_concurrency = max(1, max_concurrency)

    # Allow running the pipeline in an isolated output folder for testing, so existing
    # fetched/processed data is not affected.
    base_data_dir = Path(os.getenv("PIPELINE_DATA_DIR", str(DATA_DIR)))

    raw_dir = base_data_dir / "raw" / date_str
    processed_dir = base_data_dir / "processed" / date_str
    digest_dir = base_data_dir / "digests" / date_str
    latest_path = base_data_dir / "digests" / "latest.json"

    ensure_dir(raw_dir)
    ensure_dir(processed_dir)
    ensure_dir(digest_dir)

    all_items = []
    sem = asyncio.Semaphore(max_concurrency)
    tasks = []
    for source in sources:
        print(f"📰 Queued {source['name']}...")
        tasks.append(asyncio.create_task(_fetch_one_source(source, sem)))

    for t in asyncio.as_completed(tasks):
        try:
            source, items = await t
        except Exception as e:
            print(f"❌ Failed to fetch a source: {e}")
            continue

        name = source.get("name", "unknown")
        if items:
            save_raw_items(raw_dir, name, items)
            for item in items:
                all_items.append(normalize_item(source, item))
            print(f"✅ {name}: {len(items)} items")
        else:
            print(f"⚠️  {name}: No items found")

    all_items = deduplicate(all_items)
    low_threshold = prefs.get("low_credibility_threshold", 50)
    if max_concurrency <= 1:
        enriched = enrich_items(all_items, low_threshold)
    else:
        enriched = await enrich_items_async(
            all_items, low_threshold, max_concurrency=max_concurrency
        )
    save_processed(processed_dir, enriched)  # This now saves with timestamp wrapper
    digest = build_digest(enriched, prefs.get("daily_digest_items", 12))
    save_digest(digest_dir, digest, latest_path)
    markdown = render_digest_markdown(digest)
    save_digest_markdown(digest_dir, markdown)

    with (base_data_dir / "digests" / "latest.meta.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(
            {"date": date_str, "count": len(enriched)}, f, ensure_ascii=False, indent=2
        )


async def run_retry_sources_async(source_names: list[str]):
    """
    Re-fetch only the specified sources, enrich their items, and merge
    them into today's existing digest.  Used by the scheduler when the
    digest already exists but some sources had 0 items (e.g. Reuters was
    blocked on the first attempt).
    """
    load_dotenv()
    sources = [
        s for s in load_sources()
        if s.get("enabled") and s.get("name") in source_names
    ]
    if not sources:
        print(f"⚠️  No matching enabled sources for retry: {source_names}")
        return

    prefs = load_preferences()
    tz_name = os.getenv("PIPELINE_TIMEZONE", prefs.get("timezone", "America/Los_Angeles"))
    date_str = today_date_str(tz_name)
    for s in sources:
        s["_tz_name"] = tz_name

    max_concurrency = int(
        os.getenv("PIPELINE_MAX_CONCURRENCY", prefs.get("max_concurrency", 3))
    )
    max_concurrency = max(1, max_concurrency)

    base_data_dir = Path(os.getenv("PIPELINE_DATA_DIR", str(DATA_DIR)))
    raw_dir = base_data_dir / "raw" / date_str
    processed_dir = base_data_dir / "processed" / date_str
    digest_dir = base_data_dir / "digests" / date_str
    latest_path = base_data_dir / "digests" / "latest.json"

    ensure_dir(raw_dir)

    # ── 1. Fetch only the missing sources ──────────────────────────────
    new_items = []
    sem = asyncio.Semaphore(max_concurrency)
    tasks = []
    for source in sources:
        print(f"📰 Retrying {source['name']}...")
        tasks.append(asyncio.create_task(_fetch_one_source(source, sem)))

    for t in asyncio.as_completed(tasks):
        try:
            source, items = await t
        except Exception as e:
            print(f"❌ Failed to fetch a source: {e}")
            continue

        name = source.get("name", "unknown")
        if items:
            save_raw_items(raw_dir, name, items)
            for item in items:
                new_items.append(normalize_item(source, item))
            print(f"✅ {name}: {len(items)} items")
        else:
            print(f"⚠️  {name}: No items found (retry also failed)")

    if not new_items:
        print("⚠️  Retry produced no new items — digest unchanged.")
        return

    # ── 2. Load existing processed items ───────────────────────────────
    existing_items = []
    processed_file = processed_dir / "items.json"
    if processed_file.exists():
        try:
            data = json.loads(processed_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "items" in data:
                existing_items = data["items"]
            elif isinstance(data, list):
                existing_items = data
        except Exception:
            pass

    # ── 3. Deduplicate new items against existing ──────────────────────
    existing_ids = {it["id"] for it in existing_items if "id" in it}
    unique_new = [it for it in new_items if it["id"] not in existing_ids]

    if not unique_new:
        print("⚠️  All retry items already existed — digest unchanged.")
        return

    print(f"🔄 Enriching {len(unique_new)} new items...")

    # ── 4. Enrich only the new items ───────────────────────────────────
    low_threshold = prefs.get("low_credibility_threshold", 50)
    if max_concurrency <= 1:
        enriched_new = enrich_items(unique_new, low_threshold)
    else:
        enriched_new = await enrich_items_async(
            unique_new, low_threshold, max_concurrency=max_concurrency
        )

    # ── 5. Merge and rebuild digest ────────────────────────────────────
    all_enriched = existing_items + enriched_new
    save_processed(processed_dir, all_enriched)
    digest = build_digest(all_enriched, prefs.get("daily_digest_items", 12))
    save_digest(digest_dir, digest, latest_path)
    markdown = render_digest_markdown(digest)
    save_digest_markdown(digest_dir, markdown)

    with (base_data_dir / "digests" / "latest.meta.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(
            {"date": date_str, "count": len(all_enriched)},
            f, ensure_ascii=False, indent=2,
        )

    print(f"✅ Retry complete — digest now has {len(all_enriched)} items "
          f"(+{len(enriched_new)} new)")


def run():
    asyncio.run(run_async())


def run_retry_sources(source_names: list[str]):
    asyncio.run(run_retry_sources_async(source_names))


if __name__ == "__main__":
    run()
