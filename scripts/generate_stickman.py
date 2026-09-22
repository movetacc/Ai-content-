"""
Draw a code-generated stickman animation for the full voiceover duration.
Writes output/clips/background.mp4 (1080x1920), which assemble_video.py then
burns captions and audio onto — same contract as the stock/AI footage path.

Free, deterministic, no external API. Actions loosely match the script's
broll_keywords so the animation has some relevance to what's being said.
"""
import glob
import json
import math
import os
import random
import shutil
import subprocess

WIDTH, HEIGHT = 1080, 1920
FPS = 20
SECONDS_PER_ACTION = 3.0
BG_COLOR = (245, 244, 238)
LINE_COLOR = (25, 25, 25)
GROUND_Y = HEIGHT * 0.72
CENTER_X = WIDTH / 2


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


# ---------------------------------------------------------------------------
# Pose library — each takes a phase t in [0, ~1] and returns joint angles.
# Angles are radians measured from straight-down (0 = hanging straight down).
# ---------------------------------------------------------------------------
def pose_idle(t: float) -> dict:
    wobble = math.sin(t * 2 * math.pi)
    return {
        "bob": wobble * 4,
        "lean": 0.0,
        "arm_l": -0.35 + 0.05 * wobble,
        "arm_r": 0.35 - 0.05 * wobble,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


def pose_walk(t: float) -> dict:
    swing = math.sin(t * 2 * math.pi)
    return {
        "bob": abs(math.sin(t * 2 * math.pi)) * 6,
        "lean": 0.0,
        "arm_l": 0.6 * swing,
        "arm_r": -0.6 * swing,
        "leg_l": 0.5 * swing,
        "leg_r": -0.5 * swing,
    }


def pose_wave(t: float) -> dict:
    wave = math.sin(t * 4 * math.pi)
    return {
        "bob": math.sin(t * 2 * math.pi) * 3,
        "lean": 0.0,
        "arm_l": -0.35,
        "arm_r": -1.8 + 0.4 * wave,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


def pose_point(t: float) -> dict:
    twitch = math.sin(t * 3 * math.pi) * 0.05
    return {
        "bob": math.sin(t * 2 * math.pi) * 2,
        "lean": 0.05,
        "arm_l": -0.35,
        "arm_r": -1.45 + twitch,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


def pose_think(t: float) -> dict:
    return {
        "bob": math.sin(t * 2 * math.pi) * 2,
        "lean": -0.05,
        "arm_l": -0.35,
        "arm_r": -2.3,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


def pose_shrug(t: float) -> dict:
    lift = 0.3 + 0.15 * math.sin(t * 2 * math.pi)
    return {
        "bob": 0.0,
        "lean": 0.0,
        "arm_l": -1.0 - lift,
        "arm_r": 1.0 + lift,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


def pose_jump(t: float) -> dict:
    height = abs(math.sin(t * 2 * math.pi)) * 30
    return {
        "bob": -height,
        "lean": 0.0,
        "arm_l": -1.6,
        "arm_r": 1.6,
        "leg_l": -0.3,
        "leg_r": 0.3,
    }


def pose_thumbs_up(t: float) -> dict:
    return {
        "bob": math.sin(t * 2 * math.pi) * 2,
        "lean": 0.0,
        "arm_l": -0.35,
        "arm_r": -1.9,
        "leg_l": -0.15,
        "leg_r": 0.15,
    }


DEFAULT_ROTATION = [
    pose_idle,
    pose_walk,
    pose_point,
    pose_think,
    pose_wave,
    pose_shrug,
    pose_jump,
    pose_thumbs_up,
]

KEYWORD_ACTION_MAP = [
    (("money", "cash", "dollar", "income", "profit", "chart", "growth"), pose_point),
    (("idea", "lightbulb", "think", "brain", "plan", "strategy"), pose_think),
    (("laptop", "computer", "typing", "phone", "screen", "desk"), pose_idle),
    (("walk", "run", "step", "journey", "path", "road"), pose_walk),
    (("win", "success", "celebrate", "trophy", "achieve"), pose_thumbs_up),
    (("confused", "question", "doubt", "unsure"), pose_shrug),
    (("excited", "hype", "jump", "energy", "fast"), pose_jump),
    (("hello", "hi", "welcome", "greet"), pose_wave),
]


def pick_action_for_keyword(keyword: str):
    lowered = keyword.lower()
    for terms, action in KEYWORD_ACTION_MAP:
        if any(term in lowered for term in terms):
            return action
    return None


def build_action_sequence(total_actions: int, keywords: list[str]):
    sequence = []
    for index in range(total_actions):
        keyword = keywords[index % len(keywords)] if keywords else ""
        matched = pick_action_for_keyword(keyword)
        if matched and (not sequence or sequence[-1] != matched):
            sequence.append(matched)
            continue
        choices = [a for a in DEFAULT_ROTATION if not sequence or a != sequence[-1]]
        sequence.append(random.choice(choices))
    return sequence


def draw_stickman(draw, angles: dict, scale: float) -> None:
    head_r = 42 * scale
    leg_len = 170 * scale
    hip_y = GROUND_Y - leg_len * 0.97  # feet land near the ground line
    neck = (CENTER_X + angles["lean"] * 20 * scale, hip_y - 220 * scale + angles["bob"])
    hip = (CENTER_X, hip_y)

    def endpoint(origin, angle, length):
        return (origin[0] + length * math.sin(angle), origin[1] + length * math.cos(angle))

    left_hand = endpoint(neck, angles["arm_l"], 130 * scale)
    right_hand = endpoint(neck, angles["arm_r"], 130 * scale)
    left_foot = endpoint(hip, angles["leg_l"], leg_len)
    right_foot = endpoint(hip, angles["leg_r"], leg_len)

    line_w = max(6, int(10 * scale))
    draw.line([neck, hip], fill=LINE_COLOR, width=line_w)
    draw.line([neck, left_hand], fill=LINE_COLOR, width=line_w)
    draw.line([neck, right_hand], fill=LINE_COLOR, width=line_w)
    draw.line([hip, left_foot], fill=LINE_COLOR, width=line_w)
    draw.line([hip, right_foot], fill=LINE_COLOR, width=line_w)

    head_center = (neck[0], neck[1] - head_r)
    draw.ellipse(
        [head_center[0] - head_r, head_center[1] - head_r, head_center[0] + head_r, head_center[1] + head_r],
        outline=LINE_COLOR,
        width=line_w,
    )


def render_frames(duration: float, keywords: list[str], frame_dir: str) -> int:
    from PIL import Image, ImageDraw

    os.makedirs(frame_dir, exist_ok=True)
    total_frames = max(1, int(duration * FPS))
    total_actions = max(1, math.ceil(duration / SECONDS_PER_ACTION))
    actions = build_action_sequence(total_actions, keywords)

    for frame_index in range(total_frames):
        t_global = frame_index / FPS
        action_index = min(int(t_global // SECONDS_PER_ACTION), len(actions) - 1)
        segment_start = action_index * SECONDS_PER_ACTION
        phase = (t_global - segment_start) / SECONDS_PER_ACTION

        image = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(image)
        draw.line([(0, GROUND_Y), (WIDTH, GROUND_Y)], fill=(210, 208, 198), width=4)

        angles = actions[action_index](phase)
        draw_stickman(draw, angles, scale=1.7)

        image.save(os.path.join(frame_dir, f"frame_{frame_index:05d}.png"))

    return total_frames


def encode_video(frame_dir: str, output_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            os.path.join(frame_dir, "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            output_path,
        ],
        check=True,
    )


if __name__ == "__main__":
    with open("output/script.json", encoding="utf-8") as file:
        data = json.load(file)

    duration = probe_duration("output/voice.mp3")
    frame_dir = "output/stickman_frames"

    print(f"Rendering {duration:.1f}s of stickman animation at {FPS}fps...")
    total_frames = render_frames(duration, data.get("broll_keywords", []), frame_dir)

    os.makedirs("output/clips", exist_ok=True)
    encode_video(frame_dir, "output/clips/background.mp4")
    shutil.rmtree(frame_dir, ignore_errors=True)

    print(f"Stickman animation ({total_frames} frames) saved to output/clips/background.mp4")
