from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
import logging
import os
from file_operations import *
import boto3
import subprocess
import shutil

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

        logging.info("Detecting nonsilent ranges for {unique_uuid}")

        nonsilent_ranges = detect_nonsilent(
            audio_segment,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold,
        )

        # Check if nonsilent_ranges is None or empty
        if nonsilent_ranges is None or len(nonsilent_ranges) == 0:
            logging.error("nonsilent_ranges is None or empty.")
            raise Exception("nonsilent_ranges is None or empty.")

        logging.info("Removing silence from video for {unique_uuid}")

        nonsilent_ranges = [
            (start - padding, end + padding) for start, end in nonsilent_ranges
        ]

        logging.info("Concatenating nonsilent ranges for {unique_uuid}")

        non_silent_subclips = [
            video.subclip(max(start / 1000, 0), min(end / 1000, video.duration))
            for start, end in nonsilent_ranges
        ]

        logging.info("Concatenating final video for {unique_uuid}")

        final_video = concatenate_videoclips(non_silent_subclips, method="compose")

        logging.info("Writing audio and video to temp files for {unique_uuid}")

        temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")
        temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

        logging.info("Writing final video to temp file for {unique_uuid}")

        final_video.write_videofile(
            temp_videofile_path,
            codec="libx264",
            audio=False,
            logger=None,
        )

        logging.info("Writing final audio to temp file for {unique_uuid}")

        audio_with_fps = final_video.audio.set_fps(video.audio.fps)
        audio_with_fps.write_audiofile(temp_audiofile_path)

        output_video_local_path = os.path.join(
            temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
        )  # Define output video local path

        cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}"'
        subprocess.run(cmd, shell=True, check=True)

        video.close()

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
