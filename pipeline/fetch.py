import json
from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.utils import ensure_dir, slugify


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
    base_netloc = urlparse(base_url).netloc
    seen = set()
    
    # Skip patterns (navigation, non-article pages)
    skip_patterns = [
        '/about', '/contact', '/subscribe', '/newsletter', '/author/',
        '/category/', '/tag/', '/search', '/privacy', '/terms', '/login',
        '/account', '/profile', '/cart', '/checkout', '/advertise',
        '/video/', '/live/', '/videos/', 'rss', 'feed'
    ]
    
    # Site-specific patterns
    is_chinese_site = '.cn' in base_netloc or 'chinese' in base_netloc.lower()
    is_hackernews = 'ycombinator.com' in base_netloc
    
    total_links = 0
    filtered_reasons = {}
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        total_links += 1
        
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        
        # Must be same domain
        if parsed.netloc != base_netloc:
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
        
        if is_chinese_site:
            # Chinese sites: must have .shtml or /202X/
            is_article = ".shtml" in path or "/202" in path
        elif is_hackernews:
            # Hacker News: item pages (discussion pages)
            is_article = "item?id=" in full
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
        links.append(full)
        
        if debug and len(links) <= 5:
            print(f"  DEBUG: Accepted '{path}'")
        
        if len(links) >= limit:
            break
    
    if debug:
        print(f"  DEBUG: Total <a> tags: {total_links}")
        print(f"  DEBUG: Filter reasons: {filtered_reasons}")
    
    return links


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
    
    try:
        response = requests.get(source["url"], headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        links = extract_links(source["url"], response.text, source.get("max_items", 15), debug=False)
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
