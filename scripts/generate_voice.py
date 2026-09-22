"""
Turn output/script.json into an MP3 voiceover with edge-tts (free, no API key).
Writes output/voice.mp3.
"""
import asyncio
import json
import os
from pathlib import Path

import edge_tts

VOICE = os.environ.get("EDGE_TTS_VOICE", "en-US-GuyNeural")
RATE = os.environ.get("EDGE_TTS_RATE", "+0%")


async def synthesize(text: str, output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE)
    await communicate.save(str(output))

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("edge-tts produced an empty audio file.")


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    full_text = f"{data['hook']} {data['script']}"
    print(f"Generating edge-tts voice with voice {VOICE}...")
    asyncio.run(synthesize(full_text, "output/voice.mp3"))
    print("Voice saved to output/voice.mp3")
