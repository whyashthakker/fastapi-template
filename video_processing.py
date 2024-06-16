from celery_config import celery_app
from remove_silence import *
from file_operations import *
from communication import *
from video_subtitle_generator import *
import zipfile
from uuid import uuid4


def create_zip_file(output_files, zip_file_path):
    with zipfile.ZipFile(zip_file_path, "w") as zipf:
        for file_path in output_files:
            zipf.write(file_path, os.path.basename(file_path))


@celery_app.task(
    name="video_processing.process_video", queue="video_processing", max_retries=2
)
def process_video(
    temp_dir,
    input_video_url,
    input_video_urls,
    email,
    unique_uuid,
    silence_threshold=-30,
    min_silence_duration=300,
    padding=300,
    userId=None,
    remove_background_noise=False,
    run_locally=False,
    run_bulk=False,
    task_type="remove_silence_video",
):
    logging.info(
        f"[VIDEO_PROCESSING_STARTING]: {input_video_url}, {unique_uuid}. [USER]: {userId}"
    )

    output_files = []
    error_messages = []

    if run_bulk:
        for input_video_url in input_video_urls:
            output_video_s3_url = None
            attempts = 0
            max_attempts = 3
            threshold_increment = -5
            error_message = None
            job_id = str(uuid4())

            logging.info(
                f"[BULK_VIDEO_PROCESSING_STARTING]: {input_video_url}, {unique_uuid}. [USER]: {userId}"
            )

            while attempts < max_attempts:
                try:
                    if task_type == "remove_silence_video":
                        local_path, _, metrics = remove_silence(
                            temp_dir,
                            input_video_url,
                            job_id,
                            silence_threshold,
                            min_silence_duration,
                            padding,
                            userId,
                            remove_background_noise,
                            generate_xml=False,
                            run_locally=run_locally,
                            run_bulk=True,
                        )
                    elif task_type == "generate_subtitles":
                        local_path, _, metrics = generate_subtitles(
                            temp_dir,
                            input_video_url,
                            job_id,
                            userId=userId,
                            run_locally=run_locally,
                            run_bulk=True,
                        )
                    else:
                        raise ValueError(f"Invalid task_type: {task_type}")

                    logging.info(
                        f"[VIDEO_PROCESSING_COMPLETED]: {local_path} {unique_uuid}."
                    )
                    output_files.append(local_path)
                    break

                except Exception as e:
                    friendly_error = handle_error(e)
                    logging.error(
                        f"Attempt {attempts + 1} failed for {input_video_url}. Error: {friendly_error}"
                    )
                    error_messages.append(
                        f"Error processing {input_video_url}: {friendly_error}"
                    )
                    if (
                        "The video does not contain any detectable audio."
                        in friendly_error
                    ):
                        break
                    else:
                        attempts += 1
                        silence_threshold += threshold_increment
                        logging.warning(
                            f"Adjusting silence threshold to {silence_threshold}. Attempt {attempts}/{max_attempts}."
                        )

        if output_files:
            zip_file_name = f"{unique_uuid}_processed_video_files.zip"
            zip_file_path = os.path.join(temp_dir, zip_file_name)
            create_zip_file(output_files, zip_file_path)

            try:
                zip_s3_path = f"{unique_uuid}_processed_video_files.zip"
                zip_presigned_url = upload_to_s3(zip_file_path, zip_s3_path, userId)

                send_email(email, zip_presigned_url, media_type="Video")
            except Exception as e:
                logging.error(f"Failed to send email. Error: {str(e)}")

            try:
                trigger_webhook(
                    unique_uuid, zip_presigned_url, input_video_urls, metrics
                )
            except Exception as e:
                logging.error(f"Failed to trigger webhook. Error: {str(e)}")

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"[TEMP_DIR_REMOVED] for {unique_uuid}")

        if error_messages:
            try:
                send_failure_webhook(
                    "\n".join(error_messages),
                    unique_uuid,
                )
            except Exception as e:
                logging.error(f"Failed to send failure webhook. Error: {str(e)}")

    else:
        output_video_s3_url = None
        attempts = 0
        max_attempts = 3
        threshold_increment = -5
        error_message = None

        while attempts < max_attempts:
            try:
                if task_type == "remove_silence_video":
                    output_video_s3_url, _, metrics = remove_silence(
                        temp_dir,
                        input_video_url,
                        unique_uuid,
                        silence_threshold,
                        min_silence_duration,
                        padding,
                        userId,
                        remove_background_noise,
                        generate_xml=False,
                        run_locally=run_locally,
                        run_bulk=False,
                    )
                    logging.info(
                        f"[VIDEO_PROCESSING_COMPLETED]: {output_video_s3_url} {unique_uuid}."
                    )
                    break
                elif task_type == "generate_subtitles":
                    output_video_s3_url, _, metrics = generate_subtitles(
                        temp_dir,
                        input_video_url,
                        unique_uuid,
                        userId=userId,
                        run_locally=run_locally,
                        run_bulk=False,
                    )
                    logging.info(
                        f"[VIDEO_TRANSCRIPTION_SUBTITLE_COMPLETE]: {unique_uuid}."
                    )
                    break

            except Exception as e:
                friendly_error = handle_error(e)
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

        if not run_locally:
            if output_video_s3_url:
                try:
                    send_email(email, output_video_s3_url, media_type="Video")
                except Exception as e:
                    logging.error(f"Failed to send email. Error: {str(e)}")

                try:
                    trigger_webhook(
                        unique_uuid, output_video_s3_url, input_video_url, metrics
                    )
                except Exception as e:
                    logging.error(f"Failed to trigger webhook. Error: {str(e)}")

            else:
                try:
                    send_failure_webhook(
                        error_message
                        or "Unknown error occurred during video processing.",
                        unique_uuid,
                    )
                except Exception as e:
                    logging.error(f"Failed to send failure webhook. Error: {str(e)}")

    return output_files


def handle_error(e):
    if str(e) == "nonsilent_ranges is None or empty.":
        friendly_error = "The video does not contain any silence."
    elif "max() arg is an empty sequence" in str(e):
        friendly_error = "The video does not contain any detectable audio."
    else:
        friendly_error = f"A processing error occurred: {str(e)}"
    return friendly_error
