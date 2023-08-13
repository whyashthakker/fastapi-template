from __future__ import print_function

# Standard libraries
import os
import tempfile
import shutil
import subprocess
import logging
import smtplib
import ssl
from uuid import uuid4
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Third-party libraries
import requests
import boto3
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

# Initialize FastAPI app
app = FastAPI()

# Set the S3 credentials and config from environment variables
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = "videosilvids"
REGION_NAME = "ap-south-1"

s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION_NAME,
)


# 3. Utility Functions


class VideoItem(BaseModel):
    input_video: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300


def download_file(url, dest_path):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        logging.info(f"Downloading file from {url} to {dest_path}")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
    except requests.RequestException as e:
        logging.error(f"Error downloading file from {url}. Error: {str(e)}")
        raise


def get_unique_filename(original_name: str) -> str:
    try:
        unique_filename = f"{uuid4()}{os.path.splitext(original_name)[1]}"
        return unique_filename
    except Exception as e:
        logging.error(
            f"Error generating unique filename for {original_name}. Error: {str(e)}"
        )
        raise


def send_email(email, video_url):
    try:
        logging.info(f"Sending email to {email} with video URL {video_url}")
        sender = os.environ.get("email_sender")
        password = os.environ.get("email_password")
        receiver = email

        subject = "Your processed video is ready!"

        # Email body with HTML
        body = f"""
        <html>
            <body>
                <h2>🎉 Your Processed Video is Ready! 🎉</h2>
                
                <p>Thank you for using VideoSilenceRemover! Your video has been processed successfully. You can:</p>
                
                <ul>
                    <li><a href="{video_url}">Download your video</a></li>
                    <li>Check the job status and download from your <a href="https://app.videosilenceremover.com/dashboard">dashboard</a></li>
                    <li>Want to process another video? <a href="https://app.videosilenceremover.com/video-silence-remover">Upload another video</a></li>
                </ul>
                
                <p>If you have any questions, feel free to reach out to our <a href="mailto:support@videosilenceremover.com">support team</a>.</p>
                
                <p>Warm Regards,</p>
                <p>VideoSilenceRemover Team</p>
            </body>
        </html>
        """

        message = MIMEMultipart("alternative")
        message["From"] = sender
        message["To"] = email
        message["Subject"] = subject

        # Convert the body from string to MIMEText object
        mime_body = MIMEText(body, "html")

        # Attach the MIMEText object to the message
        message.attach(mime_body)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, receiver, message.as_string())
    except smtplib.SMTPException as e:
        logging.error(f"Error sending email to {email}. Error: {str(e)}")
        raise


def remove_silence(
    temp_dir,
    input_video_url,
    unique_uuid,
    silence_threshold=-36,
    min_silence_duration=300,
    padding=300,
):
    try:
        logging.info(f"Starting to remove silence from video: {input_video_url}.")

        original_name = os.path.basename(input_video_url)

        input_video_local_path = os.path.join(temp_dir, original_name)

        download_file(input_video_url, input_video_local_path)

        input_video_file_name = get_unique_filename(original_name)

        # Rename the downloaded file to the unique name
        unique_video_local_path = os.path.join(temp_dir, input_video_file_name)
        os.rename(input_video_local_path, unique_video_local_path)

        os.environ["MOVIEPY_TEMP_FOLDER"] = temp_dir

        video = VideoFileClip(unique_video_local_path)

        audio = video.audio

        audio_file = os.path.join(temp_dir, "temp_audio.wav")
        audio.write_audiofile(audio_file)
        audio_segment = AudioSegment.from_file(audio_file)

        nonsilent_ranges = detect_nonsilent(
            audio_segment,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold,
        )

        # Check if nonsilent_ranges is None or empty
        if nonsilent_ranges is None or len(nonsilent_ranges) == 0:
            logging.error("nonsilent_ranges is None or empty.")
            raise Exception("nonsilent_ranges is None or empty.")

        nonsilent_ranges = [
            (start - padding, end + padding) for start, end in nonsilent_ranges
        ]

        non_silent_subclips = [
            video.subclip(max(start / 1000, 0), min(end / 1000, video.duration))
            for start, end in nonsilent_ranges
        ]

        final_video = concatenate_videoclips(non_silent_subclips, method="compose")

        temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")
        temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

        final_video.write_videofile(temp_videofile_path, codec="libx264", audio=False)

        audio_with_fps = final_video.audio.set_fps(video.audio.fps)
        audio_with_fps.write_audiofile(temp_audiofile_path)

        output_video_local_path = os.path.join(
            temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
        )  # Define output video local path

        cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}"'
        subprocess.run(cmd, shell=True, check=True)

        video.close()

        # if input_video_file_name is None:
        #     logging.error("input_video_url is None.")
        #     raise HTTPException(status_code=400, detail="input_video_url is None.")

        output_video_s3_path = (
            f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
        )

        s3.upload_file(
            output_video_local_path, BUCKET_NAME, output_video_s3_path
        )  # Upload the output video

        # Construct the output video S3 URL
        output_video_s3_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{output_video_s3_path}"

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        return output_video_s3_url, unique_uuid

    except Exception as e:
        logging.error(f"Error processing video {input_video_url}. Error: {str(e)}")
        raise


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

    # raise HTTPException(
    #     status_code=500, detail="No audio found after multiple attempts."
    # )


def trigger_webhook(unique_uuid, output_video_s3_url, error_message=None):
    try:
        webhook_url = f'{os.environ.get("NEXT_APP_URL")}/api/vsr-webhook'
        payload = {"uuid": unique_uuid, "output_video_url": output_video_s3_url}
        if error_message:
            payload["error_message"] = error_message
        headers = {"Content-Type": "application/json"}
        response = requests.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Webhook trigger failed for UUID {unique_uuid}. Error: {str(e)}")


# 4. FastAPI Routes
@app.post("/remove-silence/")
async def remove_silence_route(item: VideoItem, background_tasks: BackgroundTasks):
    input_video_url = item.input_video
    email = item.email
    silence_threshold = item.silence_threshold
    min_silence_duration = item.min_silence_duration
    padding = item.padding

    if input_video_url is None:
        logging.error("input_video_url is None.")
        trigger_webhook(None, None, error_message="Please share a valid video URL.")
        return {
            "status": "Failed to initiate video processing. Please share a valid video URL.",
            "error_message": "Please share a valid video URL.",
        }

    unique_uuid = str(uuid4())
    temp_dir = tempfile.mkdtemp()

    try:
        background_tasks.add_task(
            process_video,
            temp_dir,
            input_video_url,
            email,
            unique_uuid,
            silence_threshold,
            min_silence_duration,
            padding,
        )
    except Exception as e:
        logging.error(f"Failed to initiate video processing. Error: {str(e)}")
        trigger_webhook(unique_uuid, None, error_message=str(e))
        return {
            "status": "Failed to initiate video processing.",
            "error_message": str(e),
        }
    finally:
        # Cleanup temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    return {
        "status": "Video processing started. You will be notified by email once it's done.",
        "request_id": unique_uuid,
    }


# except Exception as e:
#     logging.error(f"Failed to initiate video processing. Error: {str(e)}")
#     raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
