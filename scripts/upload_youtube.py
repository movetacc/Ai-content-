"""
Upload output/final.mp4 to YouTube with the official YouTube Data API.
Use YOUTUBE_TOKEN_JSON in CI after completing one interactive OAuth flow.
"""
import json
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = "output/youtube_token.json"


def get_credentials() -> Credentials:
    token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
    if token_json:
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)

    if os.path.exists(TOKEN_PATH):
        return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    client_secrets = os.environ["YOUTUBE_CLIENT_SECRETS_PATH"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    credentials = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w", encoding="utf-8") as file:
        file.write(credentials.to_json())
    return credentials


def upload(video_path: str, title: str, description: str) -> str:
    youtube = build("youtube", "v3", credentials=get_credentials())
    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{description}\n\n#Shorts",
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": os.environ.get("YOUTUBE_PRIVACY_STATUS", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    response = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    ).execute()
    return response["id"]


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)
    video_id = upload("output/final.mp4", data["topic"], data["caption"])
    print(f"Uploaded to YouTube: https://youtube.com/shorts/{video_id}")
