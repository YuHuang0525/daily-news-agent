import json
import re
from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.utils import ensure_dir, now_in_timezone, slugify


def fetch_rss(source: Dict) -> List[Dict]:
    feed = feedparser.parse(source["url"])
    items = []
    for entry in feed.entries[: source.get("max_items", 20)]:
        items.append(
            {
                "title": entry.get("title"),
                "url": entry.get("link"),
                "published_at": entry.get("published"),
                "summary": entry.get("summary"),
            }
        )
    return items


def extract_links(base_url: str, html: str, limit: int, debug=False) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    secondary_links = []  # fallback if we can't collect enough "preferred" article URLs
    base_netloc = urlparse(base_url).netloc
    # Normalize domains to avoid dropping links due to www vs non-www differences
    base_netloc_norm = base_netloc.lower().lstrip("www.")
    seen = set()
    
    # Skip patterns (navigation, non-article pages)
    skip_patterns = [
        '/about', '/contact', '/subscribe', '/newsletter', '/author/',
        '/category/', '/tag/', '/topic/', '/staff/', '/search', '/privacy', '/terms', '/login',
        '/account', '/profile', '/cart', '/checkout', '/advertise',
        '/video/', '/live/', '/videos/', 'rss', 'feed'
    ]
    
    # Site-specific patterns
    is_chinese_site = '.cn' in base_netloc or 'chinese' in base_netloc.lower()
    is_hackernews = 'ycombinator.com' in base_netloc
    is_modernhealthcare = 'modernhealthcare.com' in base_netloc.lower()
    is_statnews = 'statnews.com' in base_netloc.lower()
    is_reuters = 'reuters.com' in base_netloc.lower()
    is_stanford_med = 'med.stanford.edu' in base_netloc.lower()
    
    total_links = 0
    filtered_reasons = {}
    
    # ------------------------------------------------------------------
    # Site-specific: Stanford Medicine News Center (news.html)
    # Only include the top "Latest Articles" items, not topic pages or related links.
    # ------------------------------------------------------------------
    if is_stanford_med and base_url.rstrip("/").endswith("/news.html"):
        ul = None
        # Find the "News Center: Latest Articles" heading, then the next list
        for tag in soup.find_all(["h1", "h2", "h3"]):
            txt = tag.get_text(" ", strip=True).lower()
            if txt == "news center: latest articles" or txt == "latest articles":
                ul = tag.find_next("ul", class_="cmp-list")
                break

        if ul:
            for li in ul.find_all("li", class_="cmp-list__item"):
                a = li.find("a", class_="cmp-teaser__link", href=True)
                if not a:
                    continue
                href = a.get("href", "").strip()
                if not href:
                    continue
                full = urljoin(base_url, href)
                parsed = urlparse(full)
                if parsed.fragment:
                    continue
                path = (parsed.path or "").lower()
                # Only real news articles (insights or all-news) with YYYY/MM in URL
                if not re.match(r"^/news/(insights|all-news)/20\d{2}/\d{2}/", path):
                    continue
                if not path.endswith(".html"):
                    continue
                if "/_jcr_content/" in path:
                    continue
                if full in seen:
                    continue
                seen.add(full)
                links.append(full)
                if len(links) >= limit:
                    break

        if debug:
            print(f"  DEBUG (stanford): extracted {len(links)} Latest Articles links")

        return links[:limit]

    # ------------------------------------------------------------------
    # Site-specific: Modern Healthcare latest news listing (client rendered)
    # The HTML includes embedded Arc/Fusion JSON with canonical_url fields.
    # ------------------------------------------------------------------
    if is_modernhealthcare and "/latest-news" in (urlparse(base_url).path or ""):
        # Find canonical_url values and keep only story-like ones.
        # Example: "/health-tech/mh-atrium-northwell-health-wearables-apple-samsung/"
        candidates = re.findall(r"\"canonical_url\"\s*:\s*\"(/[^\"]+)\"", html)
        for p in candidates:
            if not isinstance(p, str):
                continue
            path = p.strip()
            if not path.startswith("/"):
                continue
            if any(skip in path.lower() for skip in skip_patterns):
                continue
            # Modern Healthcare story URLs are generally /{section}/{slug}/
            segs = [s for s in path.split("/") if s]
            if len(segs) < 2:
                continue
            slug = segs[-1]
            if not (slug.startswith("mh-") or "-" in slug):
                continue
            full = urljoin(base_url, path)
            if full in seen:
                continue
            seen.add(full)
            links.append(full)
            if len(links) >= limit:
                break
        if debug:
            print(f"  DEBUG (modernhealthcare): extracted {len(links)} links from canonical_url JSON")
        return links[:limit]

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        total_links += 1
        
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.fragment:
            filtered_reasons['fragment'] = filtered_reasons.get('fragment', 0) + 1
            continue
        
        # Must be same domain (tolerate www/no-www)
        if parsed.netloc.lower().lstrip("www.") != base_netloc_norm:
            filtered_reasons['wrong_domain'] = filtered_reasons.get('wrong_domain', 0) + 1
            continue
        
        # Don't include the homepage itself
        if full.rstrip("/") == base_url.rstrip("/"):
            continue
        
        path = parsed.path.lower()
        
        # Skip common non-article pages
        if any(skip in path for skip in skip_patterns):
            filtered_reasons['skip_pattern'] = filtered_reasons.get('skip_pattern', 0) + 1
            continue
        
        # Must have a meaningful path (not just /)
        if len(path.strip("/")) < 3:
            filtered_reasons['too_short'] = filtered_reasons.get('too_short', 0) + 1
            continue
        
        # Determine if this is an article based on site type
        is_article = False
        path_segments = [seg for seg in path.split("/") if seg]
        is_preferred = False
        stat_day_prefix = None
        if is_statnews:
            base_path = urlparse(base_url).path or "/"
            if re.match(r"^/20\d{2}/\d{2}/\d{2}/?$", base_path):
                stat_day_prefix = base_path if base_path.endswith("/") else base_path + "/"
        
        if is_chinese_site:
            # Chinese sites: must have .shtml or /202X/
            is_article = ".shtml" in path or "/202" in path
        elif is_hackernews:
            # Hacker News: item pages (discussion pages)
            is_article = "item?id=" in full
        elif is_modernhealthcare:
            # Modern Healthcare: articles commonly look like /{section}/{slug}/
            # Examples: /providers/mh-cleveland-clinic-commonspirit-ai-claim-denials/
            is_article = (
                len(path_segments) >= 2
                and (path_segments[-1].startswith("mh-") or "-" in path_segments[-1])
                and len(path_segments[-1]) >= 12
            )
        elif is_statnews:
            # STAT: Prefer date-based story URLs: /YYYY/MM/DD/slug/
            # Deprioritize /feature/ trackers and other evergreen pages.
            # If we're parsing a specific day page, ONLY accept links from that day.
            if stat_day_prefix:
                if path.startswith(stat_day_prefix) and path != stat_day_prefix:
                    is_article = True
                    is_preferred = True
                else:
                    is_article = False
            elif re.match(r"^/20\d{2}/\d{2}/\d{2}/", path):
                is_article = True
                is_preferred = True
            else:
                # Allow fallback only for deep non-feature URLs (rarely needed)
                is_article = (
                    path.count("/") >= 4
                    and "/feature/" not in path
                    and "/status-list/" not in path
                    and "/events" not in path
                    and "/reports" not in path
                )
        elif is_reuters:
            # Reuters: article URLs end with a date-slug like /slug-YYYY-MM-DD/
            # Section/category pages (e.g. /world/africa/) should be skipped.
            is_article = bool(re.search(r"-\d{4}-\d{2}-\d{2}/?$", path))
        else:
            # Western news sites: look for date patterns or article indicators
            is_article = (
                "/202" in path or  # Date-based URLs (2020-2029)
                "/story/" in path or
                "/article/" in path or
                "/news/" in path or
                ("/politics/" in path and path.count("/") >= 3) or
                ("/business/" in path and path.count("/") >= 3) or
                ("/tech" in path and path.count("/") >= 3) or
                ("/world/" in path and path.count("/") >= 3) or
                ("/us/" in path and path.count("/") >= 3) or
                ("/sport" in path and path.count("/") >= 3) or
                (path.count("/") >= 4)  # Deep URLs likely to be articles
            )
        
        if not is_article:
            filtered_reasons['not_article'] = filtered_reasons.get('not_article', 0) + 1
            if debug and len(links) < 5:
                print(f"  DEBUG: Filtered '{path}' - not_article")
            continue
        
        # Avoid duplicates
        if full in seen:
            continue
        
        seen.add(full)
        if is_preferred:
            links.append(full)
        else:
            # Avoid topping up with off-scope links when parsing a STAT day page.
            if not (is_statnews and stat_day_prefix):
                secondary_links.append(full)
        
        if debug and len(links) <= 5:
            print(f"  DEBUG: Accepted '{path}'")
        
        if len(links) >= limit:
            break
    
    if debug:
        print(f"  DEBUG: Total <a> tags: {total_links}")
        print(f"  DEBUG: Filter reasons: {filtered_reasons}")
    
    # If we didn't collect enough preferred links, top up with secondary candidates.
    if len(links) < limit and secondary_links:
        for u in secondary_links:
            if u in seen and u not in links:
                links.append(u)
                if len(links) >= limit:
                    break

    return links[:limit]


def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted elements that contain non-article text
    for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
        element.decompose()
    
    # Remove common navigation/menu classes
    for element in soup.find_all(class_=['nav', 'navigation', 'menu', 'header', 'footer', 'sidebar', 'widget', 'ad', 'advertisement']):
        element.decompose()
    
    # Try to find article content in common containers
    article = None
    
    # Try various article content selectors
    selectors = [
        'article',
        '[role="main"]',
        '.article-content',
        '.post-content',
        '.entry-content',
        '.content-wrapper',
        'main',
        '#main-content',
        '.main-content'
    ]
    
    for selector in selectors:
        article = soup.select_one(selector)
        if article:
            break
    
    if article:
        # Extract text from paragraphs within the article
        paragraphs = article.find_all("p")
        # Filter out very short paragraphs (likely not content)
        text_parts = [p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        if text_parts:
            return " ".join(text_parts)
    
    # Fallback: get all paragraphs but filter better
    paragraphs = soup.find_all("p")
    text_parts = []
    for p in paragraphs[:30]:  # Check more paragraphs
        text = p.get_text(" ", strip=True)
        # Only include substantial paragraphs
        if len(text) > 30 and not any(skip in text.lower() for skip in ['cookie', 'subscribe', 'newsletter', 'menu']):
            text_parts.append(text)
    
    return " ".join(text_parts[:18])  # Limit to reasonable amount


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)
    return ""

def extract_meta_description(html: str) -> str:
    """
    Best-effort fallback when full article text isn't accessible (e.g., paywalls).
    Prefer og:description, then meta description, then JSON-LD description/articleBody.
    """
    soup = BeautifulSoup(html, "html.parser")

    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        return og["content"].strip()

    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        return md["content"].strip()

    # JSON-LD (some sites include a short description even when body is gated)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            for key in ("articleBody", "description"):
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    return ""


def fetch_webpage(source: Dict) -> List[Dict]:
    # Headers to mimic a real browser and avoid bot detection
    # Note: requests library handles gzip decompression automatically
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    # Reuters requires a Referer header to avoid 401 responses.
    if 'reuters.com' in urlparse(source.get("url", "")).netloc.lower():
        headers['Referer'] = 'https://www.google.com/'

    # For some sites, we want to fetch a specific listing page rather than homepage.
    # - STAT: use today's /YYYY/MM/DD/ day page when configured with homepage URL.
    fetch_url = source.get("url", "")
    try:
        parsed0 = urlparse(fetch_url)
        if "statnews.com" in (parsed0.netloc or "").lower():
            # If user configured homepage, auto-switch to today's day page.
            if parsed0.path in ("", "/"):
                tz_name = source.get("_tz_name") or source.get("timezone")
                today_local = now_in_timezone(tz_name)
                fetch_url = f"https://www.statnews.com/{today_local:%Y/%m/%d}/"

        response = requests.get(fetch_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        links = extract_links(fetch_url, response.text, source.get("max_items", 15), debug=False)
        print(f"  🔗 Found {len(links)} potential articles")
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout fetching {source['name']}, skipping...")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching {source['name']}: {e}")
        return []
    
    items = []
    for i, link in enumerate(links):
        try:
            article_resp = requests.get(link, headers=headers, timeout=30)
            article_resp.raise_for_status()
            article_resp.encoding = article_resp.apparent_encoding
            html = article_resp.text
            text = extract_article_text(html)
            if not text or len(text) < 120:
                # Paywalled / JS-heavy sites often still expose a usable summary in meta tags.
                fallback = extract_meta_description(html)
                if fallback and len(fallback) >= 80:
                    text = fallback
                else:
                    continue
            title = extract_title(html)
            items.append(
                {
                    "title": title or link.split("/")[-1][:120],
                    "url": link,
                    "published_at": datetime.utcnow().isoformat(),
                    "summary": text[:500],
                    "full_text": text,
                }
            )
        except Exception:
            continue
    return items


def fetch_source(source: Dict) -> List[Dict]:
    if source.get("type") == "rss":
        return fetch_rss(source)
    if source.get("type") == "webpage":
        return fetch_webpage(source)
    return []


def save_raw_items(output_dir, source_name: str, items: List[Dict]):
    ensure_dir(output_dir)
    slug = slugify(source_name)
    path = output_dir / f"{slug}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
