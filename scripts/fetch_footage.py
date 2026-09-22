"""
Get portrait video clips for the b-roll keywords in output/script.json.
Writes output/clips/clip_*.mp4.

Two sources, in order:
  1. AI-generated video via fal.ai (costs real money per clip) if FAL_API_KEY is set.
  2. Free Pexels stock footage — used automatically if fal.ai is unset, fails, or
     PEXELS_API_KEY is the only key present.
"""
import json
import os
import time

import requests

FAL_API_KEY = os.environ.get("FAL_API_KEY", "").strip()
FAL_MODEL = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/ltx-video")
AI_CLIP_COUNT = int(os.environ.get("AI_CLIP_COUNT", "4"))
FAL_POLL_TIMEOUT_S = int(os.environ.get("FAL_POLL_TIMEOUT_S", "300"))

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()


# ---------------------------------------------------------------------------
# fal.ai (paid, AI-generated video)
# ---------------------------------------------------------------------------
def generate_ai_clip(prompt: str, destination: str) -> None:
    """Submit a text-to-video job to fal.ai's queue API, poll until done, download.

    NOTE: fal.ai's exact response shape can change between models/versions. This
    was written from documentation, not tested against a live API call (this
    environment can't reach fal.run), so if field names have shifted, the error
    message below prints the raw response to make it a 30-second fix.
    """
    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json",
    }

    submit = requests.post(
        f"https://queue.fal.run/{FAL_MODEL}",
        headers=headers,
        json={"prompt": prompt, "aspect_ratio": "9:16"},
        timeout=30,
    )
    submit.raise_for_status()
    submit_data = submit.json()
    request_id = submit_data.get("request_id")
    if not request_id:
        raise RuntimeError(f"fal.ai submit response had no request_id: {submit_data}")

    status_url = f"https://queue.fal.run/{FAL_MODEL}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{FAL_MODEL}/requests/{request_id}"

    deadline = time.time() + FAL_POLL_TIMEOUT_S
    while time.time() < deadline:
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status = status_resp.json().get("status")
        if status == "COMPLETED":
            break
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"fal.ai job {request_id} failed: {status_resp.json()}")
        time.sleep(5)
    else:
        raise RuntimeError(f"fal.ai job {request_id} timed out after {FAL_POLL_TIMEOUT_S}s")

    result_resp = requests.get(result_url, headers=headers, timeout=30)
    result_resp.raise_for_status()
    result = result_resp.json()

    video_url = (
        result.get("video", {}).get("url")
        if isinstance(result.get("video"), dict)
        else None
    ) or result.get("video_url")

    if not video_url:
        raise RuntimeError(
            f"Could not find a video URL in fal.ai response, check field names: {result}"
        )

    with requests.get(video_url, stream=True, timeout=120) as video_resp:
        video_resp.raise_for_status()
        with open(destination, "wb") as file:
            for chunk in video_resp.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)


def fetch_ai_clips(keywords: list[str]) -> int:
    print(f"Generating up to {AI_CLIP_COUNT} AI video clips via fal.ai ({FAL_MODEL})...")
    saved = 0
    for keyword in keywords[:AI_CLIP_COUNT]:
        destination = f"output/clips/clip_{saved}.mp4"
        try:
            generate_ai_clip(keyword, destination)
            print(f"AI-generated clip for '{keyword}' saved to {destination}")
            saved += 1
        except Exception as exc:  # noqa: BLE001 — any failure here should fall back, not crash
            print(f"fal.ai generation failed for '{keyword}': {exc}")
    return saved


# ---------------------------------------------------------------------------
# Pexels (free, stock footage fallback)
# ---------------------------------------------------------------------------
def search_pexels_clip(keyword: str) -> str | None:
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": keyword, "orientation": "portrait", "per_page": 5},
        timeout=30,
    )
    response.raise_for_status()
    videos = response.json().get("videos", [])
    if not videos:
        return None

    files = sorted(
        videos[0].get("video_files", []),
        key=lambda item: abs((item.get("height") or 0) - 1280),
    )
    for video_file in files:
        if video_file.get("file_type") == "video/mp4" and video_file.get("link"):
            return video_file["link"]
    return None


def download(url: str, destination: str) -> None:
    with requests.get(url, stream=True, timeout=90) as response:
        response.raise_for_status()
        with open(destination, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)


def fetch_pexels_clips(keywords: list[str], start_index: int = 0) -> int:
    if not PEXELS_API_KEY:
        return 0
    print("Falling back to free Pexels stock footage...")
    saved = start_index
    for keyword in keywords:
        url = search_pexels_clip(keyword)
        if not url:
            print(f"No stock clip found for '{keyword}', skipping")
            continue
        destination = f"output/clips/clip_{saved}.mp4"
        download(url, destination)
        print(f"Saved '{keyword}' to {destination}")
        saved += 1
    return saved - start_index


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    os.makedirs("output/clips", exist_ok=True)
    keywords = data["broll_keywords"]

    saved = 0
    if FAL_API_KEY:
        saved = fetch_ai_clips(keywords)
        if saved == 0:
            print("No AI clips were generated, falling back to stock footage.")
    else:
        print("FAL_API_KEY not set, using free Pexels stock footage.")

    if saved == 0:
        saved = fetch_pexels_clips(keywords)

    if saved == 0:
        raise SystemExit(
            "No footage was obtained from fal.ai or Pexels. "
            "Check FAL_API_KEY / PEXELS_API_KEY and the fal.ai response format."
        )

    print(f"Total clips ready: {saved}")
