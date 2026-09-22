"""
Runs the full pipeline: script -> voice -> footage -> assembled video ->
upload to whichever platforms are enabled via env vars.

Env vars to control which uploads run (default: all off, so a bad step
never posts a broken video):
  PUBLISH_YOUTUBE=true
  PUBLISH_INSTAGRAM=true
  PUBLISH_TIKTOK=true
"""
"""
Runs the full pipeline: script -> voice -> footage -> assembled video ->
upload to whichever platforms are enabled via env vars.

Env vars to control which uploads run (default: all off, so a bad step
never posts a broken video):
  PUBLISH_YOUTUBE=true
  PUBLISH_INSTAGRAM=true
  PUBLISH_TIKTOK=true
"""
import os
import subprocess
import sys


def run(module: str) -> None:
    print(f"\n=== Running {module} ===")
    result = subprocess.run([sys.executable, f"scripts/{module}"])
    if result.returncode != 0:
        raise SystemExit(f"{module} failed, stopping pipeline.")


def env_true(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


if __name__ == "__main__":
    run("generate_script.py")
    run("generate_voice.py")
    run("fetch_footage.py")
    run("assemble_video.py")

    if env_true("PUBLISH_YOUTUBE"):
        run("upload_youtube.py")
    else:
        print("Skipping YouTube upload (PUBLISH_YOUTUBE not set)")

    if env_true("PUBLISH_INSTAGRAM"):
        run("upload_instagram.py")
    else:
        print("Skipping Instagram upload (PUBLISH_INSTAGRAM not set)")

    if env_true("PUBLISH_TIKTOK"):
        run("upload_tiktok.py")
    else:
        print("Skipping TikTok upload (PUBLISH_TIKTOK not set)")

    print("\nPipeline complete. Final video at output/final.mp4")
