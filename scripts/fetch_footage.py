"""
Download portrait stock footage from the Pexels Video API.
Writes output/clips/clip_*.mp4.
"""
import json
import os

import requests

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
HEADERS = {"Authorization": PEXELS_API_KEY}


def search_clip(keyword: str) -> str | None:
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=HEADERS,
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


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    os.makedirs("output/clips", exist_ok=True)
    saved = 0
    for keyword in data["broll_keywords"]:
        url = search_clip(keyword)
        if not url:
            print(f"No clip found for '{keyword}', skipping")
            continue
        destination = f"output/clips/clip_{saved}.mp4"
        download(url, destination)
        print(f"Saved '{keyword}' to {destination}")
        saved += 1

    if saved == 0:
        raise SystemExit("No stock footage was downloaded. Check PEXELS_API_KEY and keywords.")
