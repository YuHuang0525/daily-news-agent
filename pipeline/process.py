import json
import hashlib
from typing import Dict, List

from dateutil import parser as dateparser

from pipeline.llm import analyze_intent, summarize_bilingual
from pipeline.score import add_corroboration, compute_credibility, credibility_label
from pipeline.utils import ensure_dir, slugify


def normalize_item(source: Dict, item: Dict) -> Dict:
    title = item.get("title") or ""
    url = item.get("url") or ""
    published = item.get("published_at") or ""
    try:
        published = dateparser.parse(published).isoformat() if published else ""
    except Exception:
        published = ""

    text = item.get("full_text") or item.get("summary") or ""
    hash_input = f"{title}|{url}".encode("utf-8")
    item_id = hashlib.sha1(hash_input).hexdigest()[:12]

    return {
        "id": item_id,
        "title": title,
        "url": url,
        "published_at": published,
        "source": source.get("name"),
        "language": source.get("language"),
        "region": source.get("region"),
        "tags": source.get("tags", []),
        "text": text,
        "source_credibility": source.get("credibility_baseline", 60),
    }


def deduplicate(items: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)
    return unique


def enrich_items(items: List[Dict], low_threshold: int) -> List[Dict]:
    items = add_corroboration(items)
    enriched = []
    total = len(items)
    
    print(f"\n🔄 Processing {total} articles with AI analysis...")
    print("━" * 60)
    
    for idx, item in enumerate(items, 1):
        # Progress bar
        progress = idx / total
        bar_length = 40
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        percent = int(progress * 100)
        
        # Print progress bar on same line
        print(f"\r[{bar}] {percent}% ({idx}/{total}) - {item.get('title', 'Processing')[:40]}...", end="", flush=True)
        
        score = compute_credibility(item["source_credibility"], item["corroboration"])
        label = credibility_label(score)
        summary = summarize_bilingual(item["text"][:4000])
        item.update(
            {
                "summary_en": summary.get("summary_en"),
                "summary_zh": summary.get("summary_zh"),
                "implication_en": summary.get("implication_en"),
                "implication_zh": summary.get("implication_zh"),
                "credibility_score": score,
                "credibility_label": label,
                "lane": "low" if score < low_threshold else "primary",
            }
        )
        if item["lane"] == "low":
            intent = analyze_intent(item["text"][:3000])
            item["intent_en"] = intent.get("intent_en")
            item["intent_zh"] = intent.get("intent_zh")
        enriched.append(item)
    
    # Print newline after progress bar
    print(f"\r[{'█' * bar_length}] 100% ({total}/{total}) - Complete!{' ' * 50}")
    print("━" * 60)
    print(f"✅ Successfully processed {total} articles\n")
    
    return enriched


def save_processed(output_dir, items: List[Dict]):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ensure_dir(output_dir)
    path = output_dir / "items.json"
    
    # Use PST/PDT timezone (America/Los_Angeles handles both automatically)
    pst = ZoneInfo('America/Los_Angeles')
    pst_time = datetime.now(pst)
    
    data_with_meta = {
        "timestamp": pst_time.isoformat(),
        "items": items
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data_with_meta, f, ensure_ascii=False, indent=2)


def build_digest(items: List[Dict], daily_limit: int) -> Dict:
    primary = [i for i in items if i["lane"] == "primary"]
    low = [i for i in items if i["lane"] == "low"]
    primary_sorted = sorted(
        primary, key=lambda x: x.get("credibility_score", 0), reverse=True
    )
    low_sorted = sorted(low, key=lambda x: x.get("credibility_score", 0))
    return {
        "date": items[0].get("published_at", "")[:10] if items else "",
        "primary": primary_sorted[:daily_limit],
        "low_credibility": low_sorted[: min(5, len(low_sorted))],
    }


def save_digest(output_dir, digest: Dict, latest_path):
    ensure_dir(output_dir)
    digest_path = output_dir / "digest.json"
    with digest_path.open("w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    with latest_path.open("w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)


def render_digest_markdown(digest: Dict) -> str:
    lines = []
    lines.append(f"# Daily Digest {digest.get('date', '')}")
    lines.append("")
    lines.append("## 15-minute brief")
    lines.append("")
    for item in digest.get("primary", []):
        lines.append(f"### {item.get('title', '')}")
        lines.append(f"- Source: {item.get('source', '')}")
        lines.append(
            f"- Credibility: {item.get('credibility_label', '')} ({item.get('credibility_score', 0)})"
        )
        lines.append(f"- EN: {item.get('summary_en', '')}")
        lines.append(f"- ZH: {item.get('summary_zh', '')}")
        lines.append(f"- Implication EN: {item.get('implication_en', '')}")
        lines.append(f"- Implication ZH: {item.get('implication_zh', '')}")
        lines.append("")
    lines.append("## Narrative watch")
    lines.append("")
    for item in digest.get("low_credibility", []):
        lines.append(f"### {item.get('title', '')}")
        lines.append(f"- Source: {item.get('source', '')}")
        lines.append(
            f"- Credibility: {item.get('credibility_label', '')} ({item.get('credibility_score', 0)})"
        )
        lines.append(f"- EN: {item.get('summary_en', '')}")
        lines.append(f"- ZH: {item.get('summary_zh', '')}")
        lines.append(f"- Intent EN: {item.get('intent_en', '')}")
        lines.append(f"- Intent ZH: {item.get('intent_zh', '')}")
        lines.append("")
    return "\n".join(lines)


def save_digest_markdown(output_dir, markdown: str):
    ensure_dir(output_dir)
    path = output_dir / "digest.bilingual.md"
    with path.open("w", encoding="utf-8") as f:
        f.write(markdown)
