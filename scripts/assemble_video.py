"""
Render a 1080x1920 video from stock clips and an AI voiceover, then burn captions.
Requires ffmpeg and ffprobe. Writes output/final.mp4.
"""
import glob
import json
import math
import os
import subprocess


def probe_duration(path: str) -> float:
    result = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        text=True,
    )
    return float(result.strip())


def build_background(clips: list[str], target_duration: float, output_path: str) -> None:
    os.makedirs("output/clips", exist_ok=True)
    scaled_clips: list[str] = []
    for index, clip in enumerate(clips):
        scaled_name = f"scaled_{index}.mp4"
        scaled_path = os.path.abspath(os.path.join("output/clips", scaled_name))
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                clip,
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                scaled_path,
            ],
            check=True,
        )
        scaled_clips.append(scaled_path)

    sequence: list[str] = []
    duration = 0.0
    while duration < target_duration:
        for clip in scaled_clips:
            sequence.append(clip)
            duration += probe_duration(clip)
            if duration >= target_duration:
                break

    concat_list = os.path.abspath("output/clips/concat.txt")
    with open(concat_list, "w", encoding="utf-8") as file:
        for clip in sequence:
            safe_path = clip.replace("'", "'\\''")
            file.write(f"file '{safe_path}'\n")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-t",
            str(target_duration),
            "-c",
            "copy",
            "-fflags",
            "+genpts",
            output_path,
        ],
        check=True,
    )


def seconds_to_srt_timestamp(value: float) -> str:
    milliseconds = int(round((value - math.floor(value)) * 1000))
    total_seconds = int(math.floor(value))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def build_srt(script: str, duration: float, output_path: str, words_per_chunk: int = 6) -> None:
    words = script.split()
    chunks = [
        " ".join(words[index : index + words_per_chunk])
        for index in range(0, len(words), words_per_chunk)
    ]
    seconds_per_chunk = duration / max(len(chunks), 1)

    with open(output_path, "w", encoding="utf-8") as file:
        for index, chunk in enumerate(chunks):
            start = index * seconds_per_chunk
            end = (index + 1) * seconds_per_chunk
            file.write(f"{index + 1}\n")
            file.write(
                f"{seconds_to_srt_timestamp(start)} --> {seconds_to_srt_timestamp(end)}\n"
            )
            file.write(f"{chunk}\n\n")


def burn_captions_and_audio(background: str, audio: str, srt: str, output_path: str) -> None:
    subtitle_path = os.path.abspath(srt).replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Arial,FontSize=14,Bold=1,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=120"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            background,
            "-i",
            audio,
            "-vf",
            f"subtitles='{subtitle_path}':force_style='{style}'",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-shortest",
            output_path,
        ],
        check=True,
    )


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    audio_duration = probe_duration("output/voice.mp3")
    clips = sorted(glob.glob("output/clips/clip_*.mp4"))
    if not clips:
        raise SystemExit("No stock clips found. Run fetch_footage.py first.")

    build_background(clips, audio_duration, "output/clips/background.mp4")
    full_script = f"{data['hook']} {data['script']}"
    build_srt(full_script, audio_duration, "output/captions.srt")
    burn_captions_and_audio(
        "output/clips/background.mp4",
        "output/voice.mp3",
        "output/captions.srt",
        "output/final.mp4",
    )
    print("Final video: output/final.mp4")
