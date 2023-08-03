import requests
import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import tempfile
import shutil
import subprocess
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import logging

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
    input_video: str  # This should be a URL


def download_file(url, dest_path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)


def remove_silence(
    input_video_url,  # Changed variable name to represent any URL
    silence_threshold=-35,
    min_silence_duration=300,
    padding=200,
    progress_callback=None,
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
        raise ValueError("input_video_file_name is None")

    print(os.path.splitext(input_video_file_name)[0])

    output_video_s3_path = f"{os.path.splitext(input_video_file_name)[0]}_output{os.path.splitext(input_video_file_name)[1]}"

    print(output_video_s3_path)

    print(output_video_local_path)
    print(BUCKET_NAME)
    print(output_video_s3_path)

    s3.upload_file(
        output_video_local_path, BUCKET_NAME, output_video_s3_path
    )  # Upload the output video

    # Construct the output video S3 URL
    output_video_s3_url = (
        f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{output_video_s3_path}"
    )

    shutil.rmtree(temp_dir)

    return output_video_s3_url


@app.post("/remove-silence/")
async def remove_silence_route(item: VideoItem):
    logging.info("Starting process to remove silence.")
    input_video_url = item.input_video  # Changed variable name to represent any URL

    if input_video_url is None:
        logging.error("input_video_url is None.")
        raise HTTPException(status_code=400, detail="input_video_url is None.")

    try:
        output_video_s3_url = remove_silence(input_video_url)  # Changed to pass any URL
        return {"output_video": output_video_s3_url}
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
