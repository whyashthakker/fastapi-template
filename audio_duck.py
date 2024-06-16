import math
from pydub import AudioSegment
from pydub.silence import detect_silence
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
def duck_audio(
    temp_dir,
    input_audio_url,
    unique_uuid,
    background_audio_url,
    gain_during_overlay=-10,
    output_format="wav",
    userId=None,
    run_bulk=False,
):
    try:
        logging.info(f"[AUDIO_DUCK_FUNCTION_STARTED]: {unique_uuid}.")

        gain_during_ducking = gain_during_overlay

        original_name = os.path.basename(input_audio_url.split("?")[0])
        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".wav"

        input_audio_local_path = os.path.join(temp_dir, original_name)
        download_file(input_audio_url, input_audio_local_path)

        background_audio_name = os.path.basename(background_audio_url.split("?")[0])
        background_audio_name = sanitize_filename(background_audio_name)

        _, bg_file_extension = os.path.splitext(background_audio_name)
        if not bg_file_extension:
            background_audio_name += ".wav"

        background_audio_local_path = os.path.join(temp_dir, background_audio_name)
        download_file(background_audio_url, background_audio_local_path)

        main_audio = AudioSegment.from_file(input_audio_local_path)
        background_audio = AudioSegment.from_file(background_audio_local_path)

        # Repeat the background audio if it's shorter than the main audio
        if len(background_audio) < len(main_audio):
            background_audio *= math.ceil(len(main_audio) / len(background_audio))
        # Trim the background audio if it's longer than the main audio
        background_audio = background_audio[: len(main_audio)]

        # Set the initial volume of the background audio
        background_volume = -20
        background_audio = background_audio + background_volume

        # Find the sections where the main audio is silent
        silence_threshold = -50  # Adjust this value as needed
        silence_duration = 1000  # Adjust this value as needed (in milliseconds)
        silent_sections = detect_silence(
            main_audio,
            min_silence_len=silence_duration,
            silence_thresh=silence_threshold,
            seek_step=1,  # Adjust this value as needed for performance
        )

        # Invert the silent sections to find the non-silent sections
        non_silent_sections = []
        start = 0
        for silence_start, silence_end in silent_sections:
            if start < silence_start:
                non_silent_sections.append((start, silence_start))
            start = silence_end
        if start < len(main_audio):
            non_silent_sections.append((start, len(main_audio)))

        # Create a copy of the background audio for ducking
        ducked_background = background_audio

        # Iterate over the non-silent sections and apply ducking to the background audio
        for start, end in non_silent_sections:
            ducked_background = ducked_background.overlay(
                main_audio[start:end],
                position=start,
                gain_during_overlay=gain_during_ducking,
            )

        # Overlay the ducked background audio onto the main audio
        ducked_audio = main_audio.overlay(ducked_background)

        output_audio_local_path = os.path.join(
            temp_dir, f"output_{unique_uuid}.{output_format}"
        )
        ducked_audio.export(output_audio_local_path, format=output_format)

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

        # Compute metrics for audio
        metrics = 0

        return file_path, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing audio {input_audio_url}. Error: {str(e)}")
        raise
