# AI Content Bot

Fully automated pipeline: generates a script → AI voice → stock footage → captioned video → uploads to YouTube Shorts, Instagram Reels, and TikTok, on a daily schedule, for $0 in compute (runs on GitHub Actions).

## Read this first — the honest platform reality

Not all three platforms are equally automatable. Be aware before you build on top of this:

| Platform | Automation reality |
|---|---|
| **YouTube Shorts** | Fully automatable, free, official API. No approval needed for your own channel. |
| **Instagram Reels** | Automatable via Meta Graph API **for your own account** without full App Review (Review is only required if other people will use your app). Requires an Instagram **Business or Creator** account linked to a Facebook Page. Needs the video hosted at a public URL first (see `upload_instagram.py`). |
| **TikTok** | TikTok's Content Posting API requires **app audit approval** from TikTok before it can post publicly on a schedule. Until audited, videos can only be uploaded as **private/draft** — you'd still tap "post" yourself in the app. Real public auto-posting takes a multi-week TikTok review. Faking it with browser automation (Selenium/Playwright) violates TikTok's ToS and risks a ban — not recommended. |

**Realistic MVP:** fully automate YouTube + Instagram now. Apply for TikTok API access in parallel (`developers.tiktok.com`); until approved, the bot still generates the TikTok-ready video file, you just tap upload manually (takes 30 seconds/day).

## What it needs (all free tier)

- **OpenRouter** API key — script generation (free models available)
- **Pexels** API key — free stock footage
- **edge-tts** — free AI voice, no API key needed
- **ffmpeg** — free, open source, video assembly (GitHub Actions runners have it preinstalled)
- **YouTube Data API** — OAuth credentials from Google Cloud Console (free)
- **Instagram Graph API** — access token from Meta Developer app (free) + a public place to host the finished video temporarily (GitHub repo raw URL under 100MB works fine for Shorts-length clips, or Cloudflare R2 free tier for more headroom)
- **TikTok Content Posting API** — apply at developers.tiktok.com (free, approval takes time)

## Setup

1. `pip install -r requirements.txt`
2. Fill in the secrets listed in `.github/workflows/daily-content.yml` under your repo's Settings → Secrets → Actions
3. Push to GitHub. The workflow runs daily at the scheduled time and can also be triggered manually from the Actions tab.

## Pipeline

```
generate_script.py   → topic + ~45s script + b-roll keywords (JSON)
generate_voice.py    → script → voice.mp3 (edge-tts)
fetch_footage.py     → keywords → 3-5 stock clips (Pexels)
assemble_video.py    → clips + voice + captions → final.mp4
upload_youtube.py    → final.mp4 → YouTube Shorts
upload_instagram.py  → final.mp4 (via public URL) → Instagram Reels
upload_tiktok.py     → final.mp4 → TikTok (draft until API is audited)
```

`main.py` runs all of the above in order, controlled by which platforms you enable via env vars.

## Caption quality note

Captions are timed by evenly dividing the script over the audio's actual duration — no transcription needed, so no extra cost or compute. If you want word-perfect captions later, swap in `faster-whisper` (free, runs locally, just slower on CPU-only GitHub runners).
