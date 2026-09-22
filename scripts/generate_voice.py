"""
Turn output/script.json into an MP3 voiceover with edge-tts (free, no API key).
Writes output/voice.mp3.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import edge_tts

VOICE = os.environ.get("EDGE_TTS_VOICE", "en-US-AndrewMultilingualNeural")
RATE = os.environ.get("EDGE_TTS_RATE", "+8%")
PITCH = os.environ.get("EDGE_TTS_PITCH", "+0Hz")
MAX_ATTEMPTS = 4


async def synthesize_once(text: str, output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(str(output))

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("edge-tts produced an empty audio file.")


async def synthesize(text: str, output_path: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await synthesize_once(text, output_path)
            return
        except Exception as exc:  # edge-tts's websocket handshake can fail transiently
            last_error = exc
            wait = min(2**attempt, 20)
            print(
                f"edge-tts attempt {attempt}/{MAX_ATTEMPTS} failed ({exc}), "
                f"retrying in {wait}s",
                file=sys.stderr,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(wait)
    raise SystemExit(f"edge-tts failed after {MAX_ATTEMPTS} attempts: {last_error}")


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    full_text = f"{data['hook']} {data['script']}"
    print(f"Generating edge-tts voice with voice {VOICE}...")
    asyncio.run(synthesize(full_text, "output/voice.mp3"))
    print("Voice saved to output/voice.mp3")
