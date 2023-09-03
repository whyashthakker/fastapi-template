import subprocess
import json
import logging
import math


def get_video_duration(url: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        url,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    output = json.loads(result.stdout)

    logging.info(f"FFprobe output: {output}")
    logging.info(f"FFprobe stderr: {result.stderr}")

    if "format" not in output or "duration" not in output["format"]:
        # Log the unexpected output for debugging
        print(f"Unexpected ffprobe output: {output}")

        # You can either raise an exception or return a default value.
        # Here, raising an exception to indicate something went wrong.
        raise ValueError("Failed to retrieve video duration from ffprobe output.")

    logging.info(f"Video duration: {float(output['format']['duration'])}")

    return float(output["format"]["duration"])


def has_sufficient_credits(video_url: str, available_credits: float) -> bool:
    duration = get_video_duration(video_url)
    return available_credits > duration


def calculate_cost(duration: float) -> int:
    return math.ceil(duration / 60)
