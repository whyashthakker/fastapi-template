from celery_config import celery_app
from remove_silence import *
from file_operations import *
from communication import *


@celery_app.task(
    name="video_processing.process_video", queue="video_processing", max_retries=2
)
def process_video(
    temp_dir,
    input_video_url,
    email,
    unique_uuid,
    silence_threshold=-30,
    min_silence_duration=300,
    padding=300,
    userId=None,
):
    logging.info(
        f"[VIDEO_PROCESSING_STARTING]: {input_video_url}, {unique_uuid}. [USER]: {userId}"
    )

    output_video_s3_url = None
    attempts = 0
    max_attempts = 3
    threshold_increment = -5
    error_message = None  # To capture the error message

    while attempts < max_attempts:
        try:
            output_video_s3_url, _, metrics = remove_silence(
                temp_dir,
                input_video_url,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
                userId,
            )
            logging.info(f"[VIDEO_PROCESSING_COMPLETED]: {unique_uuid}.")
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

    if output_video_s3_url:
        try:
            send_email(email, output_video_s3_url)
        except Exception as e:
            logging.error(f"Failed to send email. Error: {str(e)}")

        try:
            trigger_webhook(unique_uuid, output_video_s3_url, input_video_url, metrics)
        except Exception as e:
            logging.error(f"Failed to trigger webhook. Error: {str(e)}")

    else:
        try:
            send_failure_webhook(
                error_message or "Unknown error occurred during video processing."
            )
        except Exception as e:
            logging.error(f"Failed to send failure webhook. Error: {str(e)}")


@celery_app.task(name="video_processing.process_audio", queue="audio_test")
def process_audio():
    return "hello"
