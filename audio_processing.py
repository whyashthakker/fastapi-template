from celery_config import celery_app
from file_operations import *
from communication import *
from audio_silence import *


@celery_app.task(
    name="audio_processing.process_audio", queue="audio_processing", max_retries=2
)
def process_audio(
    temp_dir,
    input_audio_url,
    email,
    unique_uuid,
    silence_threshold=-30,
    min_silence_duration=300,
    padding=300,
    userId=None,
    remove_background_noise=False,
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
            output_audio_s3_url = remove_silence_audio(
                temp_dir,
                input_audio_url,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
                userId,
                remove_background_noise,
            )
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
            send_email(email, output_audio_s3_url)
        except Exception as e:
            logging.error(f"Failed to send email. Error: {str(e)}")

        try:
            trigger_webhook(unique_uuid, output_audio_s3_url, input_audio_url)
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
