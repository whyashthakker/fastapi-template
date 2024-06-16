import os
from pydub import AudioSegment
import logging
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process
from utils.metrics import compute_audio_metrics
from file_operations import *

# Load the environment variables
load_dotenv()


@safe_process
def merge_audio_files(
    temp_dir,
    input_audio_urls,
    unique_uuid,
    output_format="wav",
    userId=None,
    run_bulk=False,
):
    try:
        logging.info(f"[AUDIO_MERGE_FUNCTION_STARTED]: {unique_uuid}.")

        # Initialize an empty AudioSegment
        merged_audio = AudioSegment.empty()

        for index, input_audio_url in enumerate(input_audio_urls):
            original_name = os.path.basename(input_audio_url.split("?")[0])
            original_name = sanitize_filename(original_name)

            _, file_extension = os.path.splitext(original_name)
            if not file_extension:
                original_name += ".wav"

            input_audio_local_path = os.path.join(
                temp_dir, f"input_{index}_{original_name}"
            )
            download_file(input_audio_url, input_audio_local_path)

            audio_segment = AudioSegment.from_file(input_audio_local_path)
            merged_audio += audio_segment

        output_audio_local_path = os.path.join(
            temp_dir, f"output_{unique_uuid}.{output_format}"
        )

        merged_audio.export(output_audio_local_path, format=output_format)

        logging.info(f"[AUDIO_EXPORTED]: {unique_uuid}.")

        output_audio_s3_path = f"{unique_uuid}_output.{output_format}"

        if run_bulk:
            file_path = output_audio_local_path
        else:
            output_audio_s3_path = f"{unique_uuid}_output.{output_format}"
            presignedUrl = upload_to_s3(
                output_audio_local_path, output_audio_s3_path, userId
            )
            file_path = presignedUrl

        logging.info(f"[AUDIO_UPLOADED]: {unique_uuid}.")

        # if os.path.exists(temp_dir):
        #     shutil.rmtree(temp_dir)

        # # Compute metrics for the merged audio
        metrics = 0

        return file_path, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error merging audio files. Error: {str(e)}")
        raise
