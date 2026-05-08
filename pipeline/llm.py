import os
from typing import Dict

import json
import re

from openai import OpenAI
import asyncio


def get_default_model() -> str:
    # Read at call-time so `.env` loaded later (e.g. in `pipeline/run_daily.py`) is respected.
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def build_prompt(text: str) -> str:
    return (
        "You are a bilingual news analyst. Summarize the article in English and "
        "Chinese. Provide a one-sentence implication in both languages. Keep it "
        "concise, factual, and neutral.\n\n"
        "Return ONLY a JSON object with keys: summary_en, summary_zh, "
        "implication_en, implication_zh. No markdown, no code fences.\n\n"
        f"Article:\n{text}"
    )


def parse_json_block(text: str) -> Dict[str, str]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return {}
    return {}


def summarize_bilingual(text: str) -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "summary_en": text[:240] + "...",
            "summary_zh": "(请设置 OPENAI_API_KEY 以生成中文摘要)",
            "implication_en": "(Set OPENAI_API_KEY for implications)",
            "implication_zh": "(请设置 OPENAI_API_KEY 以生成影响分析)",
        }

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=get_default_model(),
            messages=[{"role": "user", "content": build_prompt(text)}],
            temperature=0.2,
        )
    finally:
        client.close()
    output_text = response.choices[0].message.content or ""
    parsed = parse_json_block(output_text)
    if parsed:
        return parsed
    else:
        return {
            "summary_en": output_text[:240],
            "summary_zh": "(模型输出未解析为 JSON)",
            "implication_en": "(Check model output)",
            "implication_zh": "(请检查模型输出)",
        }


def build_intent_prompt(text: str) -> str:
    return (
        "You analyze low-credibility news to infer possible narrative intent. "
        "Return concise bilingual output.\n\n"
        "Return ONLY a JSON object with keys: intent_en, intent_zh. "
        "No markdown, no code fences.\n\n"
        f"Item:\n{text}"
    )


def analyze_intent(text: str) -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "intent_en": "(Set OPENAI_API_KEY to analyze intent)",
            "intent_zh": "(请设置 OPENAI_API_KEY 以生成叙事意图分析)",
        }

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=get_default_model(),
            messages=[{"role": "user", "content": build_intent_prompt(text)}],
            temperature=0.3,
        )
    finally:
        client.close()
    output_text = response.choices[0].message.content or ""
    parsed = parse_json_block(output_text)
    if parsed:
        return parsed
    else:
        return {
            "intent_en": output_text[:200],
            "intent_zh": "(模型输出未解析为 JSON)",
        }


async def summarize_bilingual_async(text: str) -> Dict[str, str]:
    """
    Async wrapper around `summarize_bilingual` for concurrent pipelines.
    Uses a thread to avoid requiring an async OpenAI client.
    """
    return await asyncio.to_thread(summarize_bilingual, text)


async def analyze_intent_async(text: str) -> Dict[str, str]:
    """
    Async wrapper around `analyze_intent` for concurrent pipelines.
    Uses a thread to avoid requiring an async OpenAI client.
    """
    return await asyncio.to_thread(analyze_intent, text)
