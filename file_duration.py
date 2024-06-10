import subprocess
import json
import logging
from typing import Union, List


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


def get_total_duration(urls: Union[str, List[str]]) -> float:
    """
    Gets the total duration of one or multiple audio or video files using ffprobe.
    """
    if isinstance(urls, str):
        urls = [urls]

    total_duration = 0.0

    for url in urls:
        duration = get_media_duration(url)
        total_duration += duration

    return total_duration


def has_sufficient_credits(
    media_urls: Union[str, List[str]], available_credits: float
) -> bool:
    total_duration = get_total_duration(media_urls)
    return available_credits > total_duration


def calculate_cost(duration: float) -> float:
    cost = (duration / 60) * 1.5
    return round(cost, 2)
