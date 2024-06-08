import math
from pydub import AudioSegment
import logging
import os
from file_operations import *
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process
from utils.metrics import compute_audio_metrics

# Load the environment variables
load_dotenv()


@safe_process
def loop_audio(
    temp_dir,
    input_audio_url,
    unique_uuid,
    loop_count=None,
    loop_duration=None,
    output_format="wav",
    userId=None,
):
    try:
        logging.info(f"[AUDIO_LOOP_FUNCTION_STARTED]: {unique_uuid}.")

        original_name = os.path.basename(input_audio_url.split("?")[0])
        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".wav"

        input_audio_local_path = os.path.join(temp_dir, original_name)
        download_file(input_audio_url, input_audio_local_path)

        audio_segment = AudioSegment.from_file(input_audio_local_path)

        original_duration = len(audio_segment) / 1000  # pydub works in milliseconds

        if loop_count:
            looped_audio = audio_segment * loop_count
        elif loop_duration:
            loop_count = math.ceil(loop_duration / original_duration)
            looped_audio = audio_segment * loop_count
        else:
            raise ValueError("Either loop_count or loop_duration must be provided.")

        output_audio_local_path = os.path.join(temp_dir, f"output.{output_format}")
        looped_audio.export(output_audio_local_path, format=output_format)

        logging.info(f"[AUDIO_EXPORTED]: {unique_uuid}.")

        output_audio_s3_path = f"{unique_uuid}_output.{output_format}"

        presignedUrl = upload_to_s3(
            output_audio_local_path, output_audio_s3_path, userId
        )

        logging.info(f"[AUDIO_UPLOADED]: {unique_uuid}.")

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        # Compute metrics for audio based on loop count and original duration
        metrics = {
            "original_duration": original_duration,
            "loop_count": loop_count,
            "final_duration": original_duration * loop_count,
        }

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing audio {input_audio_url}. Error: {str(e)}")
        raise
