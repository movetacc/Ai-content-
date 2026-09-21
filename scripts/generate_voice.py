"""
Turn output/script.json into an AI voiceover with edge-tts.
Writes output/voice.mp3.
"""
import asyncio
import json
import os

import edge_tts

VOICE = os.environ.get("TTS_VOICE", "en-US-GuyNeural")
RATE = os.environ.get("TTS_RATE", "+8%")


async def synthesize(text: str, output_path: str) -> None:
    communicator = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicator.save(output_path)


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    full_text = f"{data['hook']} {data['script']}"
    os.makedirs("output", exist_ok=True)
    asyncio.run(synthesize(full_text, "output/voice.mp3"))
    print("Voice saved to output/voice.mp3")
