"""
Generate a short-form video script and b-roll search terms using OpenRouter.
Writes output/script.json.
"""
import json
import os
import re
import sys

import requests

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL = os.environ.get("SCRIPT_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
NICHE = os.environ.get("CONTENT_NICHE", "AI side hustles and making money with AI")

PROMPT = f"""You write scripts for short-form faceless videos (TikTok, YouTube Shorts, and Reels)
about {NICHE}.

Return only valid JSON, with no markdown fences, in exactly this shape:
{{
  "topic": "short catchy title",
  "hook": "first line that grabs attention in under three seconds",
  "script": "100-130 spoken words, conversational, one clear payoff, soft follow CTA",
  "caption": "short social caption with 3-5 relevant hashtags",
  "broll_keywords": ["keyword one", "keyword two", "keyword three", "keyword four"]
}}

Use simple, visual, stock-footage-searchable terms for broll_keywords.
"""


def generate() -> dict:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.9,
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Model did not return valid JSON: {raw}", file=sys.stderr)
        raise ValueError("OpenRouter response was not valid JSON") from exc

    required = {"topic", "hook", "script", "caption", "broll_keywords"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Script JSON is missing keys: {sorted(missing)}")
    if not isinstance(data["broll_keywords"], list) or not data["broll_keywords"]:
        raise ValueError("broll_keywords must be a non-empty list")
    return data


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    script_data = generate()
    with open("output/script.json", "w", encoding="utf-8") as file:
        json.dump(script_data, file, indent=2, ensure_ascii=False)
    print(f"Generated script: {script_data['topic']}")
