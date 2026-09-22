"""
Turn output/script.json into an MP3 voiceover with the ElevenLabs API.
Writes output/voice.mp3.
"""
import json
import os
from pathlib import Path

import requests

API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ["ELEVENLABS_VOICE_ID"]
MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
OUTPUT_FORMAT = "mp3_44100_128"


def synthesize(text: str, output_path: str) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    response = requests.post(
        url,
        headers={
            "xi-api-key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.2,
                "use_speaker_boost": True,
            },
        },
        params={"output_format": OUTPUT_FORMAT},
        timeout=120,
    )

    if not response.ok:
        detail = response.text[:500]
        raise RuntimeError(
            f"ElevenLabs TTS failed with HTTP {response.status_code}: {detail}"
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)
    if output.stat().st_size == 0:
        raise RuntimeError("ElevenLabs returned an empty audio response.")


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    full_text = f"{data['hook']} {data['script']}"
    print(f"Generating ElevenLabs voice with voice ID {VOICE_ID[:6]}...")
    synthesize(full_text, "output/voice.mp3")
    print("Voice saved to output/voice.mp3")
