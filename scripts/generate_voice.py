"""
Turn output/script.json into an AI voiceover with edge-tts.
Writes output/voice.mp3 and retries transient Edge TTS connection failures.
"""
import asyncio
import json
import os
from pathlib import Path

import edge_tts

VOICE = os.environ.get("TTS_VOICE", "en-US-AvaMultilingualNeural")
RATE = os.environ.get("TTS_RATE", "+8%")
MAX_ATTEMPTS = 3


async def synthesize(text: str, output_path: str) -> None:
    last_error: Exception | None = None
    output = Path(output_path)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if output.exists():
                output.unlink()
            print(f"Generating voice with {VOICE} (attempt {attempt}/{MAX_ATTEMPTS})")
            communicator = edge_tts.Communicate(text, VOICE, rate=RATE)
            await communicator.save(output_path)
            if not output.exists() or output.stat().st_size == 0:
                raise RuntimeError("Edge TTS returned an empty audio file.")
            return
        except Exception as error:
            last_error = error
            if output.exists():
                output.unlink()
            print(f"Edge TTS attempt {attempt} failed: {type(error).__name__}: {error}")
            if attempt < MAX_ATTEMPTS:
                delay = 2 ** attempt
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"Edge TTS failed after {MAX_ATTEMPTS} attempts using voice {VOICE}."
    ) from last_error


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    full_text = f"{data['hook']} {data['script']}"
    os.makedirs("output", exist_ok=True)
    asyncio.run(synthesize(full_text, "output/voice.mp3"))
    print("Voice saved to output/voice.mp3")
