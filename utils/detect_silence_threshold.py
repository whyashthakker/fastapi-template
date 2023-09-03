import subprocess
import re
import logging


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
    silence_threshold = mean_volume - 5

    logging.info(f"Computed silence threshold: {silence_threshold}")

    return silence_threshold


def compute_dynamic_silence_threshold(audio_path, chunk_duration=30):
    """
    Computes a dynamic silence threshold based on chunks of the audio.
    Also takes into consideration the noise floor at the beginning of the audio.
    """
    # Get the total duration of the audio
    audio_duration_cmd = (
        f'ffprobe -i {audio_path} -show_format -v quiet | sed -n "s/duration=//p"'
    )
    audio_duration = float(subprocess.getoutput(audio_duration_cmd).strip())

    # Estimate noise floor from the beginning
    noise_duration = 2.0  # seconds
    cmd_noise = f'ffmpeg -i {audio_path} -t {noise_duration} -af "volumedetect" -f null /dev/null'
    process_noise = subprocess.Popen(
        cmd_noise, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    output_noise, _ = process_noise.communicate()
    output_noise = output_noise.decode("utf-8")
    mean_volume_noise_match = re.search(
        r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", output_noise
    )
    if mean_volume_noise_match:
        mean_volume_noise = float(mean_volume_noise_match.group(1))
    else:
        logging.error(f"FFmpeg output: {output_noise}")
        raise ValueError(
            "Unable to extract mean volume from FFmpeg output for noise estimation."
        )

    thresholds = []

    # Segment the audio into chunks and compute threshold for each chunk
    num_chunks = int(audio_duration // chunk_duration)
    for i in range(num_chunks):
        start_time = i * chunk_duration
        end_time = (i + 1) * chunk_duration
        cmd_chunk = f'ffmpeg -i {audio_path} -ss {start_time} -to {end_time} -af "volumedetect" -f null /dev/null'
        process_chunk = subprocess.Popen(
            cmd_chunk, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output_chunk, _ = process_chunk.communicate()
        output_chunk = output_chunk.decode("utf-8")
        mean_volume_chunk_match = re.search(
            r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", output_chunk
        )
        if mean_volume_chunk_match:
            mean_volume_chunk = float(mean_volume_chunk_match.group(1))
            thresholds.append(
                mean_volume_chunk - 5
            )  # Adjust this value based on testing
        else:
            thresholds.append(
                mean_volume_noise - 5
            )  # Use noise floor estimation if chunk volume not found

    # Return the average threshold across chunks
    return sum(thresholds) / len(thresholds) if thresholds else mean_volume_noise - 5


# Replace the call to compute_silence_threshold in remove_silence function with compute_dynamic_silence_threshold
# silence_threshold = compute_dynamic_silence_threshold(audio_file)

# Note: The user feedback and fine-tuning would require additional frontend/backend mechanisms and are not implemented here.
