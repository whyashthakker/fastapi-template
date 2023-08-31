import subprocess
import re
import ffmpeg
import logging
import os


def compute_silence_threshold(audio_path):
    # Use FFmpeg to get the volume levels
    cmd = f'ffmpeg -i {audio_path} -af "volumedetect" -f null /dev/null'

    # Redirect the FFmpeg output directly to a variable
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    output, _ = process.communicate()
    output = output.decode("utf-8")

    # Modify the regex to be more lenient
    mean_volume_match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", output)
    if mean_volume_match:
        mean_volume = float(mean_volume_match.group(1))
    else:
        logging.error(
            f"FFmpeg output: {output}"
        )  # Log the entire FFmpeg output for debugging
        raise ValueError("Unable to extract mean volume from FFmpeg output.")

    # Set the silence threshold to be slightly above the mean volume (e.g., 5 dB more)
    silence_threshold = mean_volume - 8

    return silence_threshold
