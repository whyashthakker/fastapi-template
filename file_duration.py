import subprocess
import json
import logging


def get_media_duration(url: str) -> float:
    """
    Gets the duration of an audio or video file using ffprobe.
    """
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
        logging.error(f"Unexpected ffprobe output: {output}")
        raise ValueError("Failed to retrieve media duration from ffprobe output.")

    logging.info(f"Media duration: {float(output['format']['duration'])}")

    return float(output["format"]["duration"])


def has_sufficient_credits(media_url: str, available_credits: float) -> bool:
    duration = get_media_duration(media_url)
    return available_credits > duration


def calculate_cost(duration: float) -> float:
    cost = (duration / 60) * 1.5
    return round(cost, 2)
