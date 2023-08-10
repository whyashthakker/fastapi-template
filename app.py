from __future__ import print_function
import requests
import boto3
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import os
import tempfile
import shutil
import subprocess
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import logging
import smtplib
from email.message import EmailMessage
import ssl
from uuid import uuid4
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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


class VideoItem(BaseModel):
    input_video: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300


def download_file(url, dest_path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)


def send_email(email, video_url):
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


def remove_silence(
    input_video_url,
    unique_uuid,
    silence_threshold=-36,
    min_silence_duration=300,
    padding=300,
):
    logging.info(f"Starting to remove silence from video: {input_video_url}.")
    input_video_file_name = os.path.basename(input_video_url)
    input_video_local_path = os.path.join(tempfile.gettempdir(), input_video_file_name)

    # Download the video file from any URL to local
    download_file(
        input_video_url, input_video_local_path
    )  # Changed to use the new download function

    temp_dir = tempfile.mkdtemp()
    os.environ["MOVIEPY_TEMP_FOLDER"] = temp_dir

    video = VideoFileClip(input_video_local_path)  # Use local path
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

    final_video = concatenate_videoclips(non_silent_subclips)

    temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")
    temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

    print(temp_audiofile_path)

    final_video.write_videofile(temp_videofile_path, codec="libx264", audio=False)

    audio_with_fps = final_video.audio.set_fps(video.audio.fps)
    audio_with_fps.write_audiofile(temp_audiofile_path)

    output_video_local_path = os.path.join(
        temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
    )  # Define output video local path

    cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}"'
    subprocess.run(cmd, shell=True, check=True)

    video.close()

    print(input_video_file_name)

    if input_video_file_name is None:
        logging.error("input_video_url is None.")
        raise HTTPException(status_code=400, detail="input_video_url is None.")

    output_video_s3_path = (
        f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
    )

    s3.upload_file(
        output_video_local_path, BUCKET_NAME, output_video_s3_path
    )  # Upload the output video

    # Construct the output video S3 URL
    output_video_s3_url = (
        f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{output_video_s3_path}"
    )

    print(output_video_s3_url)

    shutil.rmtree(temp_dir)

    return output_video_s3_url, unique_uuid


def process_video(
    input_video_url,
    email,
    unique_uuid,
    silence_threshold=-36,
    min_silence_duration=300,
    padding=300,
):
    attempts = 0
    max_attempts = 3
    threshold_increment = -5

    while attempts < max_attempts:
        try:
            output_video_s3_url, _ = remove_silence(
                input_video_url,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
            )
            send_email(email, output_video_s3_url)
            trigger_webhook(unique_uuid, output_video_s3_url)
            return  # Success, so return from the function

        except Exception as e:
            # If nonsilent_ranges error, try increasing the threshold
            if str(e) == "nonsilent_ranges is None or empty.":
                attempts += 1
                silence_threshold += threshold_increment
                logging.warning(
                    f"Adjusting silence threshold to {silence_threshold}. Attempt {attempts}/{max_attempts}."
                )
            else:
                # If it's a different kind of error, break out of the loop
                break

    logging.error(f"Failed to process video after {max_attempts} attempts.")
    raise HTTPException(
        status_code=500, detail="No audio found after multiple attempts."
    )


def trigger_webhook(unique_uuid, output_video_s3_url):
    webhook_url = f'{os.environ.get("NEXT_APP_URL")}/api/vsr-webhook'
    payload = {"uuid": unique_uuid, "output_video_url": output_video_s3_url}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"Webhook triggered for UUID: {unique_uuid}")
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Oops: Something went wrong {err}")


@app.post("/remove-silence/")
async def remove_silence_route(item: VideoItem, background_tasks: BackgroundTasks):
    logging.info("Starting process to remove silence.")
    input_video_url = item.input_video
    email = item.email
    silence_threshold = item.silence_threshold
    min_silence_duration = item.min_silence_duration
    padding = item.padding

    if input_video_url is None:
        logging.error("input_video_url is None.")
        raise HTTPException(status_code=400, detail="input_video_url is None.")

    unique_uuid = str(uuid4())

    # Pass the optional parameters to the background task
    background_tasks.add_task(
        process_video,
        input_video_url,
        email,
        unique_uuid,
        silence_threshold,
        min_silence_duration,
        padding,
    )

    return {
        "status": "Video processing started. You will be notified by email once it's done.",
        "request_id": unique_uuid,
    }
