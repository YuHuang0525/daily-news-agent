from typing import Dict, List


def credibility_label(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "low"
    return "very-low"


def compute_credibility(source_baseline: int, corroboration_count: int) -> int:
    score = source_baseline + min(corroboration_count * 5, 20)
    return max(0, min(100, score))


def add_corroboration(items: List[Dict]) -> List[Dict]:
    title_map = {}
    for item in items:
        key = (item.get("title") or "").lower()[:80]
        title_map.setdefault(key, 0)
        title_map[key] += 1
    for item in items:
        key = (item.get("title") or "").lower()[:80]
        item["corroboration"] = max(0, title_map.get(key, 1) - 1)
    return items
