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

# from utils.safeprocess import safe_process
from utils.file_standardiser import convert_to_standard_format
from utils.metrics import compute_video_metrics
from utils.detect_silence_threshold import (
    compute_silence_threshold,
    compute_dynamic_silence_threshold,
)

# Load the environment variables
load_dotenv()


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
        logging.info(f"[REMOVE_SILENCE_FUNCTION_STARTED]: {unique_uuid}.")

        # Determine original_name based on the URL extension
        original_name = os.path.basename(input_video_url.split("?")[0])

        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".mp4"  # Add the file extension only if not present

        input_video_local_path = os.path.join(temp_dir, original_name)
        download_file(input_video_url, input_video_local_path)

        input_video_file_name = get_unique_filename(original_name)

        unique_video_local_path = os.path.join(temp_dir, input_video_file_name)

        os.rename(input_video_local_path, unique_video_local_path)

        os.environ["MOVIEPY_TEMP_FOLDER"] = temp_dir

        unique_video_local_path = convert_to_standard_format(
            unique_video_local_path, temp_dir
        )

        video = VideoFileClip(unique_video_local_path)

        audio = video.audio
        audio_file = os.path.join(temp_dir, "temp_audio.wav")

        audio.write_audiofile(audio_file, logger=None)

        audio_segment = AudioSegment.from_file(audio_file)

        # silence_threshold = compute_dynamic_silence_threshold(audio_file)

        logging.info(f"[SILENCE_THRESHOLD]: {silence_threshold}")

        loop_counter = 0
        while loop_counter < 2:
            nonsilent_ranges = detect_nonsilent(
                audio_segment,
                min_silence_len=min_silence_duration,
                silence_thresh=silence_threshold,
            )

            nonsilent_ranges = [
                (start - padding, end + padding) for start, end in nonsilent_ranges
            ]

            non_silent_subclips = []
            for start, end in nonsilent_ranges:
                start_time = max(start / 1000, 0)
                end_time = min(end / 1000, video.duration)
                subclip = video.subclip(start_time, end_time)
                non_silent_subclips.append(subclip)

            logging.info(
                f"[NON_SILENT_SUBCIPS_EXTRACTION_DONE_CONCATENATING]: {unique_uuid}"
            )

            final_video = concatenate_videoclips(non_silent_subclips, method="compose")

            # Determine durations for comparison
            original_duration = video.duration
            final_duration = final_video.duration

            logging.info(
                f"[ORIGINAL_DURATION]: {original_duration} [FINAL_DURATION]: {final_duration}"
            )

            if (
                original_duration > final_duration
                and original_duration * 0.93 > final_duration
            ):
                break

            silence_threshold = compute_silence_threshold(audio_file)
            loop_counter += 1

        temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

        temp_audiofile_path = os.path.join(
            temp_dir, "temp_audio_for_video_conversion.mp3"
        )

        logging.info(f"[WRITING_FINAL_VIDEO]: {unique_uuid}")

        final_video.write_videofile(
            temp_videofile_path,
            codec="libx264",
            bitrate="1500k",
            threads=os.environ.get("PROCESS_THREADS"),
            preset="faster",
            audio_bitrate="128k",
            audio_fps=44100,
            write_logfile=False,
            logger=None,
            temp_audiofile=temp_audiofile_path,
        )

        metrics = compute_video_metrics(video, final_video, nonsilent_ranges)

        audio_with_fps = final_video.audio.set_fps(video.audio.fps)

        temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")

        audio_with_fps.write_audiofile(temp_audiofile_path, logger=None)

        output_video_local_path = os.path.join(
            temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
        )

        cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}" -loglevel error'
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

        video.close()

        output_video_s3_path = (
            f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
        )

        original_video_s3_path = (
            f"{unique_uuid}_original{os.path.splitext(input_video_file_name)[1]}"
        )

        upload_to_s3(
            unique_video_local_path, original_video_s3_path, userId, folder="original"
        )

        logging.info(f"[UPLOADING_TO_S3]: {unique_uuid}")

        presignedUrl = upload_to_s3(
            output_video_local_path, output_video_s3_path, userId
        )

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing video {input_video_url}. Error: {str(e)}")
        raise
