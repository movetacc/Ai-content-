"""
Upload output/final.mp4 with TikTok's official Content Posting API.
Until TikTok approves the app for public posting, uploads are private drafts.
"""
import json
import os

import requests

ACCESS_TOKEN = os.environ["TIKTOK_ACCESS_TOKEN"]
API_BASE = "https://open.tiktokapis.com/v2"


def init_upload(video_path: str, caption: str) -> dict:
    video_size = os.path.getsize(video_path)
    response = requests.post(
        f"{API_BASE}/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "post_info": {
                "title": caption[:150],
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"]


def upload_video_bytes(upload_url: str, video_path: str) -> None:
    with open(video_path, "rb") as file:
        video_bytes = file.read()
    response = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{len(video_bytes) - 1}/{len(video_bytes)}",
        },
        data=video_bytes,
        timeout=180,
    )
    response.raise_for_status()


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)
    init_data = init_upload("output/final.mp4", data["caption"])
    upload_video_bytes(init_data["upload_url"], "output/final.mp4")
    print(
        "Sent to TikTok as a draft "
        f"(publish ID: {init_data['publish_id']}). Review it in TikTok before posting."
    )
