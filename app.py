import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# Optional dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data" / "digests"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

app = Flask(__name__, static_folder="static", template_folder="templates")


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


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages with AI-powered responses.
    
    This endpoint processes user questions about the daily digest
    and provides contextual responses.
    """
    data = request.get_json()
    message = data.get("message", "")
    history = data.get("history", [])
    digest_context = data.get("digest_context", {})
    
    # Try to use OpenAI if available
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if openai_key:
        try:
            import openai
            
            client = openai.OpenAI(api_key=openai_key)
            
            # Build context from digest
            news_context = ""
            if digest_context and digest_context.get("primary"):
                news_items = []
                for item in digest_context["primary"][:5]:  # Top 5 items
                    news_items.append(
                        f"- {item.get('title', 'Untitled')}: "
                        f"{item.get('summary_en', '')} "
                        f"(Tags: {', '.join(item.get('tags', []))})"
                    )
                news_context = "\n".join(news_items)
            
            system_prompt = f"""You are a helpful assistant for a daily news digest app focused on tech, finance, and global politics with China/US emphasis. 

Today's top stories:
{news_context}

Help users understand these stories, their implications, and connections. Be concise but insightful. When relevant, mention credibility considerations."""

            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add history (last 6 messages)
            for msg in history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
            )
            
            reply = response.choices[0].message.content
            return jsonify({"reply": reply})
            
        except Exception as e:
            # Fall through to fallback response
            print(f"OpenAI error: {e}")
    
    # Fallback intelligent response without API
    reply = generate_fallback_response(message, digest_context)
    return jsonify({"reply": reply})


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
    app.run(host="127.0.0.1", port=8000, debug=True)
