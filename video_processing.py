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
    remove_background_noise=False,
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
                remove_background_noise,
            )
            logging.info(
                f"[VIDEO_PROCESSING_COMPLETED]: {output_video_s3_url} {unique_uuid}."
            )
            break

        except Exception as e:
            # Check for the specific error and replace it with a more user-friendly message
            if str(e) == "nonsilent_ranges is None or empty.":
                friendly_error = "The video does not contain any silence."
            elif "max() arg is an empty sequence" in str(e):
                friendly_error = "The video does not contain any detectable audio."
            else:
                friendly_error = f"A processing error occurred: {str(e)}"

            logging.error(f"Attempt {attempts + 1} failed. Error: {friendly_error}")
            error_message = friendly_error

            if "The video does not contain any detectable audio." in friendly_error:
                break
            else:
                attempts += 1
                silence_threshold += threshold_increment
                logging.warning(
                    f"Adjusting silence threshold to {silence_threshold}. Attempt {attempts}/{max_attempts}."
                )

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logging.info(f"[TEMP_DIR_REMOVED] for {unique_uuid}")

    if output_video_s3_url:
        try:
            send_email(email, output_video_s3_url, media_type="Video")
        except Exception as e:
            logging.error(f"Failed to send email. Error: {str(e)}")

        try:
            trigger_webhook(unique_uuid, output_video_s3_url, input_video_url, metrics)
        except Exception as e:
            logging.error(f"Failed to trigger webhook. Error: {str(e)}")

    else:
        try:
            send_failure_webhook(
                error_message or "Unknown error occurred during video processing.",
                unique_uuid,
            )
        except Exception as e:
            logging.error(f"Failed to send failure webhook. Error: {str(e)}")
