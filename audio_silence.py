from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import logging
import os
from file_operations import *
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process

# from utils.safeprocess import safe_process
from utils.metrics import compute_audio_metrics
from utils.detect_silence_threshold import compute_silence_threshold

from background_noise import denoise_audio_spectral_subtraction

# from background_noise import clean_background_noise

# Load the environment variables
load_dotenv()


@safe_process
def remove_silence_audio(
    temp_dir,
    input_audio_url,
    unique_uuid,
    silence_threshold=-50,
    min_silence_duration=300,
    padding=100,
    userId=None,
    remove_background_noise=False,
):
    try:
        logging.info(f"[AUDIO_REMOVE_SILENCE_FUNCTION_STARTED]: {unique_uuid}.")

        original_name = os.path.basename(input_audio_url.split("?")[0])
        print(original_name)
        original_name = sanitize_filename(original_name)

        print(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".wav"

        input_audio_local_path = os.path.join(temp_dir, original_name)
        download_file(input_audio_url, input_audio_local_path)

        converted_audio_path = os.path.join(temp_dir, "converted_to_wav.wav")
        audio_segment = AudioSegment.from_file(input_audio_local_path)
        audio_segment.export(converted_audio_path, format="wav")

        # # If remove_background_noise is True, process the audio to remove noise
        if remove_background_noise:
            denoised_audio_file = denoise_audio_spectral_subtraction(
                converted_audio_path
            )
            audio_segment = AudioSegment.from_file(denoised_audio_file)

        else:
            audio_segment = AudioSegment.from_file(input_audio_local_path)

        loop_counter = 0

        while loop_counter < 2:
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

            # Determine durations for comparison
            original_duration = len(audio_segment) / 1000  # pydub works in milliseconds
            final_duration = len(concatenated_audio) / 1000

            if (
                original_duration > final_duration
                and final_duration < 0.85 * original_duration
            ):
                logging.info(f"silence_threshold: {silence_threshold}")
                break

            silence_threshold = compute_silence_threshold(input_audio_local_path)
            logging.info(f"silence_threshold: {silence_threshold}")
            loop_counter += 1

        output_audio_local_path = os.path.join(temp_dir, "output" + file_extension)
        concatenated_audio.export(output_audio_local_path, format="wav")

        logging.info(f"[AUDIO_EXPORTED]: {unique_uuid}.")

        output_audio_s3_path = f"{unique_uuid}_output.wav"

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
        metrics = compute_audio_metrics(original_duration, nonsilent_ranges)

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing audio {input_audio_url}. Error: {str(e)}")
        raise
