"""
Generate a short-form video script and b-roll search terms using OpenRouter.
Writes output/script.json.
"""
import json
import os
import re
import sys
import time

import requests

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
NICHE = os.environ.get("CONTENT_NICHE", "AI side hustles and making money with AI")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

# Claude 3.5 Haiku is cheap (a script here runs well under a cent) and writes far more
# naturally than the free 8B models. If it fails (bad key, no credits, outage) or you'd
# rather not spend anything, fall back to free models so the pipeline never just dies.
PRIMARY_MODEL = os.environ.get("SCRIPT_MODEL", "anthropic/claude-3.5-haiku")
FALLBACK_MODELS = [
    model
    for model in [
        PRIMARY_MODEL,
        "openai/gpt-4o-mini",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ]
    if model
]
# Dedupe while keeping order.
FALLBACK_MODELS = list(dict.fromkeys(FALLBACK_MODELS))

MAX_RETRIES_PER_MODEL = 3


def fetch_trending_context(niche: str) -> str:
    """Web search for current stories in the niche via Tavily. Returns "" (never
    raises) if TAVILY_API_KEY isn't set or the search fails — the script still
    generates fine without it, just without real-time grounding.
    """
    if not TAVILY_API_KEY:
        return ""

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": f"latest trending news and stories about {niche}",
                "topic": "news",
                "search_depth": "basic",
                "max_results": 5,
                "days": 3,
            },
            timeout=30,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return ""

        lines = []
        for item in results[:5]:
            title = (item.get("title") or "").strip()
            snippet = (item.get("content") or "")[:200].strip()
            if title:
                lines.append(f"- {title}: {snippet}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 — never let a search hiccup break the pipeline
        print(f"Trend search failed, continuing without it: {exc}", file=sys.stderr)
        return ""


def build_prompt(trending_context: str) -> str:
    trending_block = ""
    if trending_context:
        trending_block = f"""
Here are real, current stories related to this niche from the last few days:
{trending_context}

Where it fits naturally, ground the script in one of these specific current stories or
numbers instead of a generic timeless tip — that's what makes it feel current, not recycled.
Don't force it or fabricate details beyond what's given above; if none of these fit, write
a strong evergreen script instead.
"""

    return f"""You write scripts for short-form faceless videos (TikTok, YouTube Shorts, and Reels)
about {NICHE}.
{trending_block}
Write like a real person telling a friend something useful they just learned — specific,
opinionated, a little blunt. NOT like an AI-generated listicle.

Never use these overused AI-script patterns:
- "Are you tired of..." / "Are you struggling with..." / "Ever wonder why..."
- "In today's video, we're going to..." / "Let's dive in" / "Without further ado"
- "In this fast-paced world" / "In today's digital age" / hollow "picture this" openers
- Vague hype with no content: "game-changer," "unlock your potential," "level up your life,"
  "this one trick," "secret nobody tells you"
- Generic CTAs like "smash that follow button" or "let me know in the comments"

Instead:
- Hook with a specific, concrete claim, number, or contradiction in the first sentence —
  something a viewer could fact-check or picture, not a vague tease.
- Give one real, specific piece of information (a tool name, a number, a step, a mistake) —
  not generic motivational filler.
- End with a soft, specific CTA tied to what you just said, not a generic "follow for more."

Return only valid JSON, with no markdown fences, in exactly this shape:
{{
  "topic": "short catchy title",
  "hook": "first line: a specific, concrete claim or number, not a vague tease, under 3 seconds spoken",
  "script": "100-130 spoken words, conversational, one real specific payoff, soft specific CTA",
  "caption": "short social caption with 3-5 relevant hashtags",
  "broll_keywords": ["keyword one", "keyword two", "keyword three", "keyword four"]
}}

For broll_keywords: use concrete, literal, physically filmable nouns that appear or are directly
implied in the script (e.g. "person typing laptop", "stack of cash close up", "phone screen scrolling") —
never abstract concepts like "success" or "growth" that have no literal visual.
"""


def call_model(model: str, prompt: str) -> requests.Response:
    return requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        },
        timeout=60,
    )


def parse_response(response: requests.Response) -> dict:
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


def generate() -> dict:
    last_error: Exception | None = None
    trending_context = fetch_trending_context(NICHE)
    if trending_context:
        print("Found current trending context, grounding script in it.")
    prompt = build_prompt(trending_context)

    for model in FALLBACK_MODELS:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            response = call_model(model, prompt)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(2 ** attempt * 5, 60)
                print(
                    f"[{model}] rate limited (429), attempt {attempt}/{MAX_RETRIES_PER_MODEL}, "
                    f"waiting {wait:.0f}s"
                )
                time.sleep(wait)
                last_error = requests.exceptions.HTTPError(f"429 from {model}")
                continue

            try:
                response.raise_for_status()
                return parse_response(response)
            except (requests.exceptions.HTTPError, ValueError) as exc:
                print(f"[{model}] failed: {exc}", file=sys.stderr)
                last_error = exc
                break  # try next model rather than retrying a non-429 failure

    raise SystemExit(
        f"All models failed after retries: {last_error}. "
        "This is usually OpenRouter's free-tier rate limit — try again in a few minutes, "
        "or set SCRIPT_MODEL to a paid model if this keeps happening."
    )


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    script_data = generate()
    with open("output/script.json", "w", encoding="utf-8") as file:
        json.dump(script_data, file, indent=2, ensure_ascii=False)
    print(f"Generated script: {script_data['topic']}")
