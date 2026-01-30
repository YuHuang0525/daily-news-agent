import ipaddress
import json as json_module
import os
import re
import socket
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

# Optional dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Model selection (read from environment; defaults kept for backwards compatibility)
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data" / "digests"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
ARTICLES_DIR = ROOT_DIR / "data" / "articles"


# ---------------------------------------------------------------------------
# Article fetch / extract / cache helpers
# ---------------------------------------------------------------------------

def _is_private_host(hostname: str) -> bool:
    """Return True if the hostname resolves to a private/loopback IP."""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except Exception:
        return True  # fail closed


def _safe_fetch_html(url: str, timeout: int = 10, max_bytes: int = 2_000_000) -> str:
    """Fetch HTML from a URL with basic SSRF protection."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed")
    if not parsed.hostname or _is_private_host(parsed.hostname):
        raise ValueError("Blocked host (private/invalid)")

    headers = {"User-Agent": "daily-news-agent/1.0 (+local)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()

    content = r.content[:max_bytes]
    return content.decode(r.encoding or "utf-8", errors="replace")


def _extract_main_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:50000]  # cap at 50k chars


def _article_cache_path(date_str: str, item_id: str) -> Path:
    return ARTICLES_DIR / date_str / f"{item_id}.json"


def _load_cached_article(date_str: str, item_id: str) -> Optional[str]:
    p = _article_cache_path(date_str, item_id)
    if p.exists():
        try:
            return json_module.loads(p.read_text(encoding="utf-8")).get("text")
        except Exception:
            return None
    return None


def _save_cached_article(date_str: str, item_id: str, url: str, text: str) -> None:
    p = _article_cache_path(date_str, item_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json_module.dumps({"id": item_id, "url": url, "text": text}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_and_cache_article(date_str: str, item_id: str, url: str) -> Optional[str]:
    """Fetch article, extract text, cache it, and return the text (or None on failure)."""
    try:
        html = _safe_fetch_html(url)
        text = _extract_main_text(html)
        if text:
            _save_cached_article(date_str, item_id, url, text)
        return text
    except Exception as e:
        print(f"[fetch_article] Failed to fetch {url}: {e}")
        return None

app = Flask(__name__, static_folder="static", template_folder="templates")

def _active_openai_model() -> str:
    # Read at call-time so `.env` or process env changes are reflected.
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/digest")
def digest():
    import json as json_module
    from datetime import datetime
    
    latest = DATA_DIR / "latest.json"
    digest_data = {"date": "", "primary": [], "low_credibility": [], "timestamp": None}
    
    if latest.exists():
        try:
            digest_data = json_module.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            pass
    elif (ROOT_DIR / "data" / "sample_digest.json").exists():
        try:
            sample = ROOT_DIR / "data" / "sample_digest.json"
            digest_data = json_module.loads(sample.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # Try to get timestamp from processed items
    if not digest_data.get("timestamp"):
        try:
            # Get latest processed items
            latest_meta = DATA_DIR / "latest.meta.json"
            if latest_meta.exists():
                meta = json_module.loads(latest_meta.read_text(encoding="utf-8"))
                date_str = meta.get("date", datetime.now().strftime("%Y-%m-%d"))
                processed_file = PROCESSED_DIR / date_str / "items.json"
                if processed_file.exists():
                    processed_data = json_module.loads(processed_file.read_text(encoding="utf-8"))
                    if isinstance(processed_data, dict) and "timestamp" in processed_data:
                        digest_data["timestamp"] = processed_data["timestamp"]
        except Exception:
            pass
    
    return jsonify(digest_data)


@app.route("/api/all-items")
def all_items():
    """Get all processed items with timestamp for source filtering."""
    import json as json_module
    from datetime import datetime
    
    try:
        # Get latest date
        latest_meta = DATA_DIR / "latest.meta.json"
        if latest_meta.exists():
            meta = json_module.loads(latest_meta.read_text(encoding="utf-8"))
            date_str = meta.get("date", datetime.now().strftime("%Y-%m-%d"))
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Load processed items
        processed_file = PROCESSED_DIR / date_str / "items.json"
        if processed_file.exists():
            data = json_module.loads(processed_file.read_text(encoding="utf-8"))
            
            # Handle both old and new format
            if isinstance(data, dict) and "items" in data:
                return jsonify({
                    "timestamp": data.get("timestamp"),
                    "date": date_str,
                    "items": data["items"]
                })
            elif isinstance(data, list):
                # Old format compatibility
                return jsonify({
                    "timestamp": None,
                    "date": date_str,
                    "items": data
                })
    except Exception as e:
        print(f"Error loading all items: {e}")
    
    return jsonify({"timestamp": None, "date": "", "items": []})


@app.route("/api/model")
def model_info():
    """Return the exact OpenAI model configured for this server."""
    sdk_version = None
    try:
        import openai as openai_module

        sdk_version = getattr(openai_module, "__version__", None)
    except Exception:
        pass

    return jsonify(
        {
            "openai_model": _active_openai_model(),
            "openai_sdk_version": sdk_version,
            "has_openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
        }
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages with AI-powered responses.
    
    This endpoint processes user questions about the daily digest
    and provides contextual responses.
    
    If a card is selected (active_item_id), the model focuses on that story.
    If the model determines more context is needed (2-pass), we fetch the article.
    """
    data = request.get_json()
    message = data.get("message", "")
    history = data.get("history", [])
    digest_context = data.get("digest_context", {})
    active_item_id = data.get("active_item_id")  # Selected article
    active_item = data.get("active_item")  # Optional compact selected item payload

    # If the user asks which model is being used, answer deterministically
    msg_lower = (message or "").lower().strip()
    if any(
        phrase in msg_lower
        for phrase in [
            "what model are you using",
            "which model are you using",
            "what model",
            "which model",
            "openai model",
        ]
    ):
        return jsonify(
            {
                "reply": f"This server is configured to use: {_active_openai_model()} (from OPENAI_MODEL).",
                "model": _active_openai_model(),
            }
        )

    # Gather all items from digest
    primary_items = (digest_context or {}).get("primary") or []
    low_items = (digest_context or {}).get("low_credibility") or []
    all_items = list(primary_items) + list(low_items)
    date_str = (digest_context or {}).get("date") or "unknown"

    # Debug logging
    print(
        f"[chat] active_item_id={active_item_id}, "
        f"has_active_item={bool(active_item)}, total_items={len(all_items)}"
    )

    # Find selected item if provided
    selected = None
    # Prefer explicit selected item payload from frontend (avoids id mismatches between datasets)
    if isinstance(active_item, dict) and active_item.get("title"):
        selected = active_item
    elif active_item_id:
        selected = next(
            (it for it in all_items if str(it.get("id", "")) == str(active_item_id)),
            None,
        )
        if selected:
            print(f"[chat] Found selected item: {selected.get('title', '')[:50]}")
        else:
            print(f"[chat] WARNING: active_item_id={active_item_id} not found in items")

    def _fmt_item(it: dict) -> str:
        return (
            f"Title: {it.get('title', 'Untitled')}\n"
            f"Source: {it.get('source', '')}\n"
            f"URL: {it.get('url', '')}\n"
            f"Tags: {', '.join(it.get('tags', []) or [])}\n"
            f"Summary (EN): {it.get('summary_en', '')}\n"
            f"Implication (EN): {it.get('implication_en', '')}\n"
        )

    selected_block = _fmt_item(selected) if selected else "(No article selected)"

    # Build a small "other stories" block for additional context
    other_items = [it for it in primary_items if not selected or it.get("id") != selected.get("id")]
    top_others = "\n---\n".join(_fmt_item(it) for it in other_items[:3])

    # Try to use OpenAI if available
    openai_key = os.getenv("OPENAI_API_KEY")
    model = _active_openai_model()

    if openai_key:
        try:
            import openai

            client = openai.OpenAI(api_key=openai_key)

            def _call_openai(msgs: list, token_limit: int = 500, temperature: float = 0.7) -> str:
                if model.startswith("gpt-5"):
                    resp = client.chat.completions.create(
                        model=model,
                        messages=msgs,
                        temperature=temperature,
                        extra_body={"max_completion_tokens": token_limit},
                    )
                else:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=msgs,
                        max_tokens=token_limit,
                        temperature=temperature,
                    )
                return resp.choices[0].message.content or ""

            # ------------------------------------------------------------------
            # Pass 1: Router – decide if we need to fetch the full article
            # ------------------------------------------------------------------
            needs_fetch = False
            if selected and selected.get("url") and selected.get("id"):
                router_system = (
                    "You are a routing function. Decide whether the user's question can be "
                    "answered using ONLY the provided digest snippet (title, summary, implication). "
                    "If the snippet is insufficient and fetching the full article would help, "
                    "set needs_fetch=true.\n\n"
                    "Return ONLY valid JSON with keys: needs_fetch (boolean), reason (string)."
                )
                router_user = (
                    f"SELECTED ITEM DIGEST:\n{selected_block}\n\n"
                    f"USER QUESTION:\n{message}\n"
                )
                router_msgs = [
                    {"role": "system", "content": router_system},
                    {"role": "user", "content": router_user},
                ]
                try:
                    router_raw = _call_openai(router_msgs, token_limit=150, temperature=0.0)
                    # Parse JSON from response (allow markdown fences)
                    router_raw_clean = re.sub(r"```json\s*", "", router_raw)
                    router_raw_clean = re.sub(r"```\s*", "", router_raw_clean)
                    router_json = json_module.loads(router_raw_clean)
                    needs_fetch = bool(router_json.get("needs_fetch"))
                    print(f"[router] needs_fetch={needs_fetch}, reason={router_json.get('reason','')}")
                except Exception as e:
                    print(f"[router] parse error: {e}, raw={router_raw[:200] if 'router_raw' in dir() else ''}")
                    needs_fetch = False

            # ------------------------------------------------------------------
            # Optionally fetch the article
            # ------------------------------------------------------------------
            article_text: Optional[str] = None
            if needs_fetch and selected:
                item_id = str(selected.get("id", ""))
                item_url = selected.get("url", "")
                # Try cache first
                article_text = _load_cached_article(date_str, item_id)
                if not article_text and item_url:
                    article_text = _fetch_and_cache_article(date_str, item_id, item_url)

            # ------------------------------------------------------------------
            # Pass 2: Answer the user's question
            # ------------------------------------------------------------------
            answer_system = (
                "You are a helpful assistant for a daily news digest app focused on tech, "
                "finance, and global politics with China/US emphasis.\n\n"
                "If a SELECTED ITEM is provided, prioritize answering about that item.\n"
                "If ARTICLE TEXT EXCERPT is provided, use it for deeper details.\n"
                "If details are still missing, say so honestly and answer with what is available.\n"
                "Be concise but insightful."
            )

            answer_user = f"SELECTED ITEM DIGEST:\n{selected_block}\n\n"
            if article_text:
                excerpt = article_text[:8000]  # bound prompt size
                answer_user += f"ARTICLE TEXT EXCERPT:\n{excerpt}\n\n"
            if top_others:
                answer_user += f"OTHER TOP STORIES (for background):\n{top_others}\n\n"
            answer_user += f"USER QUESTION:\n{message}\n"

            # Build full message list with history
            messages = [{"role": "system", "content": answer_system}]
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            messages.append({"role": "user", "content": answer_user})

            reply = _call_openai(messages, token_limit=600, temperature=0.7)
            return jsonify({
                "reply": reply,
                "model": model,
                "fetched_article": bool(article_text),
            })

        except Exception as e:
            print(f"OpenAI error: {e}")

    # Fallback intelligent response without API
    reply = generate_fallback_response(message, digest_context)
    return jsonify({"reply": reply, "model": model})


def generate_fallback_response(message: str, digest_context: dict) -> str:
    """Generate a helpful response without external API."""
    msg_lower = message.lower()
    
    primary = digest_context.get("primary", []) if digest_context else []
    
    if not primary:
        return "I don't have any news digest loaded. Please refresh the page to load today's news."
    
    news_count = len(primary)
    
    # Summary requests
    if any(word in msg_lower for word in ["summar", "overview", "today", "brief"]):
        titles = [f"• **{n.get('title', 'Untitled')}**" for n in primary[:5]]
        return f"""**Today's Digest Summary**

I have {news_count} high-signal stories for you today:

{chr(10).join(titles)}

Each story includes English and Chinese summaries, plus implication analysis. Would you like me to elaborate on any specific story?"""
    
    # Finance/investment questions
    if any(word in msg_lower for word in ["financ", "invest", "money", "gold", "stock", "market"]):
        finance_news = [n for n in primary if n.get("tags") and "finance" in n.get("tags", [])]
        if finance_news:
            top = finance_news[0]
            return f"""**Finance-Related Coverage**

I found {len(finance_news)} finance stories. The top one is:

**{top.get('title', 'Untitled')}**

{top.get('summary_en', 'No summary available.')}

**Implication:** {top.get('implication_en', 'Check the full article for investment implications.')}"""
        return "I didn't find specific finance stories in today's digest. Try checking the tags on each card."
    
    # China/US relations
    if any(word in msg_lower for word in ["china", "us", "america", "trade", "geopolit"]):
        relevant = [n for n in primary if 
                   "china" in n.get("summary_en", "").lower() or 
                   "us" in n.get("summary_en", "").lower() or
                   (n.get("tags") and "politics" in n.get("tags", []))]
        if relevant:
            top = relevant[0]
            return f"""**China-US Related Content**

Found {len(relevant)} potentially relevant stories:

**{top.get('title', 'Untitled')}**

{top.get('summary_en', '')}

**Implication:** {top.get('implication_en', '')}"""
        return "I didn't find explicitly China-US focused stories today, but political news often has implications for bilateral relations."
    
    # Credibility questions
    if any(word in msg_lower for word in ["credib", "reliable", "trust", "source", "corrobor"]):
        return f"""**Credibility Information**

All {news_count} stories are tagged with credibility labels:

• **High**: Well-corroborated from reliable sources
• **Medium**: Single-source or limited verification  
• **Low**: Requires skeptical reading (check Narrative Watch section)

Most of today's stories are marked as medium credibility. For important decisions, always cross-reference with primary sources."""
    
    # Tech questions
    if any(word in msg_lower for word in ["tech", "ai", "software", "digital"]):
        tech_news = [n for n in primary if n.get("tags") and "tech" in n.get("tags", [])]
        if tech_news:
            top = tech_news[0]
            return f"""**Tech Coverage**

Found {len(tech_news)} tech stories:

**{top.get('title', 'Untitled')}**

{top.get('summary_en', '')}"""
        return "Check the cards with 'tech' tags for technology-related coverage."
    
    # Default helpful response
    return f"""I'm your news digest assistant! Today I have {news_count} stories loaded.

I can help you with:
• **Summaries** - Ask for an overview of today's news
• **Finance** - Investment and market implications  
• **Geopolitics** - China-US relations and global politics
• **Credibility** - Source reliability and corroboration
• **Tech** - Technology and innovation news

What would you like to explore?"""


if __name__ == "__main__":
    import sys
    
    # Suppress Flask startup messages in debug mode
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("\n" + "=" * 70)
    print("🚀 Daily News Agent - Server Starting")
    print("=" * 70)
    print(f"\n✅ Server is running at: \033[1;36mhttp://127.0.0.1:8000\033[0m")
    print(f"\n💡 Click the link above or copy to your browser")
    print(f"⌨️  Press CTRL+C to stop the server\n")
    print("=" * 70 + "\n")
    
    try:
        app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
        sys.exit(0)
