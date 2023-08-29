from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import logging
import os
from file_operations import *
import subprocess
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process

# from utils.safeprocess import safe_process
from utils.file_standardiser import convert_to_standard_format
from utils.metrics import compute_audio_metrics

# Load the environment variables
load_dotenv()


@safe_process
def remove_silence(
    temp_dir,
    input_audio_url,
    unique_uuid,
    silence_threshold=-45,
    min_silence_duration=300,
    padding=100,
    userId=None,
):
    try:
        logging.info(f"[AUDIO_REMOVE_SILENCE_FUNCTION_STARTED]: {unique_uuid}.")

        original_name = os.path.basename(input_audio_url.split("?")[0])
        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".wav"

        input_audio_local_path = os.path.join(temp_dir, original_name)
        download_file(input_audio_url, input_audio_local_path)

        audio_segment = AudioSegment.from_file(input_audio_local_path)

        nonsilent_ranges = detect_nonsilent(
            audio_segment,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold,
        )

        nonsilent_ranges = [
            (start - padding, end + padding) for start, end in nonsilent_ranges
        ]

        logging.info(f"[NON_SILENT_RANGES_CONCATENATED]: {unique_uuid}.")

        concatenated_audio = AudioSegment.empty()

        for start, end in nonsilent_ranges:
            concatenated_audio += audio_segment[start:end]

        output_audio_local_path = os.path.join(temp_dir, "output" + file_extension)
        concatenated_audio.export(output_audio_local_path, format="wav")

        logging.info(f"[AUDIO_EXPORTED]: {unique_uuid}.")

        output_audio_s3_path = (
            f"{unique_uuid}_output{os.path.splitext(original_name)[1]}"
        )

        # original_audio_s3_path = (
        # f"{unique_uuid}_original{os.path.splitext(original_name)[1]}"
        # )

        # upload_to_s3(
        # input_audio_local_path, original_audio_s3_path, userId, folder="original"
        # )

        presignedUrl = upload_to_s3(
            output_audio_local_path, output_audio_s3_path, userId
        )

        logging.info(f"[AUDIO_UPLOADED]: {unique_uuid}.")

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        # Compute metrics for audio based on nonsilent_ranges and audio duration
        metrics = compute_audio_metrics(
            audio_segment.duration_seconds, nonsilent_ranges
        )

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing audio {input_audio_url}. Error: {str(e)}")
        raise
