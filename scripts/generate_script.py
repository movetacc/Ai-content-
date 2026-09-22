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

# The :free models share a global rate limit across every OpenRouter user, so a 429
# is expected under load, not a sign anything is broken. Try the requested model
# first, then fall back through a few other free models before giving up.
PRIMARY_MODEL = os.environ.get("SCRIPT_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
FALLBACK_MODELS = [
    model
    for model in [
        PRIMARY_MODEL,
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ]
    if model
]
# Dedupe while keeping order.
FALLBACK_MODELS = list(dict.fromkeys(FALLBACK_MODELS))

MAX_RETRIES_PER_MODEL = 3

PROMPT = f"""You write scripts for short-form faceless videos (TikTok, YouTube Shorts, and Reels)
about {NICHE}.

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


def call_model(model: str) -> requests.Response:
    return requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
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

    for model in FALLBACK_MODELS:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            response = call_model(model)

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
