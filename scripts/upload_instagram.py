"""
Publish output/final.mp4 as an Instagram Reel through Meta's Graph API.
The video must already be available at PUBLIC_VIDEO_URL.
"""
import json
import os
import time

import requests

IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
PUBLIC_VIDEO_URL = os.environ["PUBLIC_VIDEO_URL"]
GRAPH_BASE = "https://graph.facebook.com/v20.0"


def create_container(caption: str) -> str:
    response = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media",
        data={
            "media_type": "REELS",
            "video_url": PUBLIC_VIDEO_URL,
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["id"]


def wait_until_ready(container_id: str, timeout_seconds: int = 300, interval: int = 5) -> None:
    elapsed = 0
    while elapsed < timeout_seconds:
        response = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        response.raise_for_status()
        status = response.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("Instagram failed to process the Reel container.")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError("Instagram container did not finish processing in time.")


def publish(container_id: str) -> str:
    response = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["id"]


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)
    container_id = create_container(data["caption"])
    wait_until_ready(container_id)
    media_id = publish(container_id)
    print(f"Published to Instagram, media ID: {media_id}")
