from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
import logging
import os
from file_operations import *
import subprocess
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process

# from utils.safeprocess import safe_process
from utils.file_standardiser import convert_to_standard_format
from utils.metrics import compute_video_metrics

# Load the environment variables
load_dotenv()

BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
REGION_NAME = os.environ.get("AWS_REGION_NAME")

THREAD = os.environ.get("PROCESS_THREADS")


@safe_process
def remove_silence(
    temp_dir,
    input_video_url,
    unique_uuid,
    silence_threshold=-45,
    min_silence_duration=300,
    padding=100,
    userId=None,
):
    try:
        logging.info(f"Starting to remove silence from video: {input_video_url}.")

        # Determine original_name based on the URL extension
        original_name = os.path.basename(input_video_url.split("?")[0])

        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".mp4"  # Add the file extension only if not present

        input_video_local_path = os.path.join(temp_dir, original_name)
        download_file(input_video_url, input_video_local_path)

        logging.info(f"Downloaded video file for {unique_uuid}")

        input_video_file_name = get_unique_filename(original_name)

        unique_video_local_path = os.path.join(temp_dir, input_video_file_name)

        logging.info(f"Renamed video file for {unique_uuid}")

        os.rename(input_video_local_path, unique_video_local_path)

        os.environ["MOVIEPY_TEMP_FOLDER"] = temp_dir

        unique_video_local_path = convert_to_standard_format(
            unique_video_local_path, temp_dir
        )

        video = VideoFileClip(unique_video_local_path)

        logging.info(f"Extracting audio for {unique_uuid}")

        audio = video.audio
        audio_file = os.path.join(temp_dir, "temp_audio.wav")

        audio.write_audiofile(audio_file)

        logging.info(f"Audio file written for {unique_uuid}")

        audio_segment = AudioSegment.from_file(audio_file)

        nonsilent_ranges = detect_nonsilent(
            audio_segment,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold,
        )

        logging.info(f"Detected nonsilent ranges for {unique_uuid}")

        nonsilent_ranges = [
            (start - padding, end + padding) for start, end in nonsilent_ranges
        ]

        logging.info(f"Extracting nonsilent subclips for {unique_uuid}")

        non_silent_subclips = []
        for start, end in nonsilent_ranges:
            start_time = max(start / 1000, 0)
            end_time = min(end / 1000, video.duration)
            subclip = video.subclip(start_time, end_time)
            non_silent_subclips.append(subclip)

        logging.info(f"Concatenating nonsilent subclips for {unique_uuid}")

        final_video = concatenate_videoclips(non_silent_subclips, method="compose")

        temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

        logging.info(f"Writing final video to {temp_videofile_path} for {unique_uuid}")

        final_video.write_videofile(
            temp_videofile_path,
            codec="libx264",
            bitrate="1500k",
            threads=THREAD,
            preset="faster",
            audio_bitrate="128k",
            audio_fps=44100,
            write_logfile=False,
        )

        logging.info(f"Final video written for {unique_uuid}")

        metrics = compute_video_metrics(video, final_video, nonsilent_ranges)

        audio_with_fps = final_video.audio.set_fps(video.audio.fps)

        temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")

        audio_with_fps.write_audiofile(temp_audiofile_path)

        logging.info(f"Audio file written for {unique_uuid}")

        output_video_local_path = os.path.join(
            temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
        )

        logging.info(
            f"Writing output video to {output_video_local_path} for {unique_uuid}"
        )

        cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}"'
        subprocess.run(cmd, shell=True, check=True)

        logging.info(f"Output video written for {unique_uuid}")

        video.close()

        output_video_s3_path = (
            f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
        )

        original_video_s3_path = (
            f"{unique_uuid}_original{os.path.splitext(input_video_file_name)[1]}"
        )

        logging.info(
            f"Uploading original video to {original_video_s3_path} for {unique_uuid}"
        )

        upload_to_s3(
            unique_video_local_path, original_video_s3_path, userId, folder="original"
        )

        logging.info(
            f"Uploading output video to {output_video_s3_path} for {unique_uuid}"
        )

        logging.info(f"userId is {userId}")

        presignedUrl = upload_to_s3(
            output_video_local_path, output_video_s3_path, userId
        )

        logging.info(f"Uploaded output video to S3 for {unique_uuid}")

        # output_video_s3_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{output_video_s3_path}"

        # logging.info(f"Output video URL: {output_video_s3_url}")

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        logging.info(f"Deleted temp folder for {unique_uuid}")

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing video {input_video_url}. Error: {str(e)}")
        raise

    finally:
        # Close the video object if it exists
        try:
            video.close()
        except NameError:
            pass  # 'video' isn't defined, so it's safe to pass

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
