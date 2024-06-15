from celery_config import celery_app
from file_operations import *
from communication import *
from audio_silence import *
from audio_loop import *
from audio_merger import *
from bg_noise_removal import *
from ai_music_generation import *
from audio_speed import *
from audio_duck import *


@celery_app.task(
    name="audio_processing.process_audio", queue="audio_processing", max_retries=2
)
def process_audio(
    temp_dir,
    input_audio_url,
    input_audio_urls,
    email,
    unique_uuid,
    silence_threshold=-30,
    min_silence_duration=300,
    padding=300,
    userId=None,
    remove_background_noise=False,
    run_locally=False,
    run_bulk_locally=False,
    task_type="remove_silence_audio",
    loop_count=None,
    loop_duration=None,
    output_format="wav",
    noise_duration=1000,
    amplification_factor=1.5,
    text_prompt=None,
    speed_factor=1.0,
    background_audio_url=None,
    gain_during_overlay=-10,
):
    logging.info(
        f"[AUDIO_PROCESSING_STARTING]: {input_audio_url}, {unique_uuid}. [USER]: {userId}"
    )

    output_audio_s3_url = None
    attempts = 0
    max_attempts = 3
    threshold_increment = -5
    error_message = None  # To capture the error message

    while attempts < max_attempts:
        try:
            if task_type == "audio_loop":
                output_audio_s3_url, _, metrics = loop_audio(
                    temp_dir,
                    input_audio_url,
                    unique_uuid,
                    loop_count=loop_count,
                    loop_duration=loop_duration,
                    output_format=output_format,
                    userId=userId,
                )
            elif task_type == "remove_silence_audio":
                output_audio_s3_url, _, metrics = remove_silence_audio(
                    temp_dir,
                    input_audio_url,
                    unique_uuid,
                    silence_threshold,
                    min_silence_duration,
                    padding,
                    userId,
                    remove_background_noise,
                )
            elif task_type == "audio_merge":
                output_audio_s3_url, _, metrics = merge_audio_files(
                    temp_dir,
                    input_audio_urls,
                    unique_uuid,
                    output_format=output_format,
                    userId=userId,
                )
            elif task_type == "remove_noise_audio":
                output_audio_s3_url, _, metrics = remove_background_noise_from_audio(
                    temp_dir,
                    input_audio_url,
                    unique_uuid,
                    noise_duration,
                    amplification_factor,
                    userId,
                )
            elif task_type == "ai_music_generation":
                output_audio_s3_url, _, metrics = generate_music(
                    temp_dir,
                    text_prompt,
                    unique_uuid,
                    userId,
                    run_locally,
                    run_bulk_locally,
                )
            elif task_type == "audio_speed":
                output_audio_s3_url, _, metrics = change_audio_speed(
                    temp_dir,
                    input_audio_url,
                    unique_uuid,
                    speed_factor=speed_factor,
                    output_format=output_format,
                    userId=userId,
                )
            elif task_type == "audio_duck":
                output_audio_s3_url, _, metrics = duck_audio(
                    temp_dir,
                    input_audio_url,
                    unique_uuid,
                    background_audio_url,
                    gain_during_overlay=gain_during_overlay,
                    output_format=output_format,
                    userId=userId,
                )
            else:
                raise ValueError(f"Invalid task_type: {task_type}")

            logging.info(
                f"[AUDIO_PROCESSING_COMPLETED]: {output_audio_s3_url} {unique_uuid}."
            )
            break

        except Exception as e:
            logging.error(f"Attempt {attempts + 1} failed. Error: {str(e)}")
            # If nonsilent_ranges error, try increasing the threshold
            if str(e) == "nonsilent_ranges is None or empty.":
                attempts += 1
                silence_threshold += threshold_increment
                logging.warning(
                    f"Adjusting silence threshold to {silence_threshold}. Attempt {attempts}/{max_attempts}."
                )
            else:
                error_message = str(e)
                break

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logging.info(f"[TEMP_DIR_REMOVED] for {unique_uuid}")

    if output_audio_s3_url:
        try:
            send_email(email, output_audio_s3_url, media_type="Audio")
        except Exception as e:
            logging.error(f"Failed to send email. Error: {str(e)}")

        try:
            trigger_webhook(unique_uuid, output_audio_s3_url, input_audio_url, metrics)
        except Exception as e:
            logging.error(f"Failed to trigger webhook. Error: {str(e)}")

    else:
        try:
            send_failure_webhook(
                error_message or "Unknown error occurred during audio processing.",
                unique_uuid,
            )
        except Exception as e:
            logging.error(f"Failed to send failure webhook. Error: {str(e)}")
