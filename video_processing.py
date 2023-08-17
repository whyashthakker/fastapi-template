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
):
    logging.info(f"Starting to process video: {input_video_url}.")
    attempts = 0
    max_attempts = 3
    threshold_increment = -5

    while attempts < max_attempts:
        try:
            output_video_s3_url, _ = remove_silence(
                temp_dir,
                input_video_url,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
            )
            trigger_webhook(unique_uuid, output_video_s3_url)
            send_email(email, output_video_s3_url)
            logging.info(f"Finished processing video: {input_video_url}.")
            return

        except Exception as e:
            # If nonsilent_ranges error, try increasing the threshold
            if str(e) == "nonsilent_ranges is None or empty.":
                attempts += 1
                silence_threshold += threshold_increment
                logging.warning(
                    f"Adjusting silence threshold to {silence_threshold}. Attempt {attempts}/{max_attempts}."
                )
            else:
                break


@celery_app.task(name="video_processing.process_audio", queue="audio_test")
def process_audio():
    return "hello"
