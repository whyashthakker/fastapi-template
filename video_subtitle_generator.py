from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import logging
import os
from file_operations import *
import subprocess
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.file_standardiser import convert_to_standard_format
from utils.metrics import compute_video_metrics
from openai import OpenAI

# Load the environment variables
load_dotenv()

openai_api_key = os.environ.get("OPENAI_API_KEY")


def transcribe_audio_with_openai(audiofilename):
    client = OpenAI(api_key=openai_api_key)

    retries = 3
    while retries:
        try:
            with open(audiofilename, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="verbose_json",
                    timestamp_granularities=["word"],
                )

            wordlevel_info = transcript.words

            # wordlevel_info = [
            #     {"word": word.word, "start": word.start, "end": word.end}
            #     for word in transcript.words
            # ]

            return wordlevel_info
        except Exception as e:
            logging.error(f"Failed to transcribe audio due to error: {e}. Retrying...")
            retries -= 1

    if retries == 0:
        logging.error(f"Failed to transcribe audio after 3 attempts.")
        return []


def generate_subtitles(
    temp_dir,
    input_video_url,
    unique_uuid,
    userId=None,
    run_locally=False,
    run_bulk=False,
):
    try:
        logging.info(f"[GENERATE_SUBTITLES_FUNCTION_STARTED]: {unique_uuid}.")

        # Determine original_name based on the URL extension
        original_name = os.path.basename(input_video_url.split("?")[0])

        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".mp4"  # Add the file extension only if not present

        input_video_local_path = os.path.join(temp_dir, original_name)

        download_file(input_video_url, input_video_local_path, run_locally=run_locally)

        input_video_file_name = get_unique_filename(original_name)

        unique_video_local_path = os.path.join(temp_dir, input_video_file_name)

        os.rename(input_video_local_path, unique_video_local_path)

        os.environ["MOVIEPY_TEMP_FOLDER"] = temp_dir

        if not run_locally:
            unique_video_local_path = convert_to_standard_format(
                unique_video_local_path, temp_dir
            )

        video = VideoFileClip(unique_video_local_path)

        # Comment out the following line to process the entire video
        # video = video.subclip(0, 20)

        video_width, video_height = video.size

        # Determine the aspect ratio
        aspect_ratio = video_width / video_height

        # Adjust the character limit based on the aspect ratio
        if aspect_ratio < 1:  # 9:16 (vertical video)
            char_limit = 6  # Show only 1 word for vertical videos
        else:  # 16:9 or other aspect ratios
            char_limit = 50  # Show multiple words for horizontal videos

        audio = video.audio

        temp_audio_file = os.path.join(temp_dir, "temp_audio.mp3")
        audio.write_audiofile(temp_audio_file)

        # Extract subtitles from the video using OpenAI's subtitle extraction feature
        subtitles = transcribe_audio_with_openai(temp_audio_file)

        # Group subtitles into lines based on character limit
        subtitle_lines = []
        current_line = []
        current_line_char_count = 0
        current_line_start_time = None
        current_line_end_time = None
        # char_limit = 50  # Adjust this value as needed

        for subtitle in subtitles:
            start_time = subtitle["start"]
            end_time = subtitle["end"]
            word = subtitle["word"]

            if current_line_char_count == 0:
                current_line_start_time = start_time
            current_line_end_time = end_time

            if current_line_char_count + len(word) + 1 <= char_limit:
                current_line.append(word)
                current_line_char_count += len(word) + 1
            else:
                subtitle_lines.append(
                    {
                        "start": current_line_start_time,
                        "end": current_line_end_time,
                        "text": " ".join(current_line),
                    }
                )
                current_line = [word]
                current_line_char_count = len(word)
                current_line_start_time = start_time

        if current_line:
            subtitle_lines.append(
                {
                    "start": current_line_start_time,
                    "end": current_line_end_time,
                    "text": " ".join(current_line),
                }
            )

        # Generate subtitle clips with proper positioning
        subtitle_clips = []
        for subtitle_line in subtitle_lines:
            start_time = subtitle_line["start"]
            end_time = subtitle_line["end"]
            text = subtitle_line["text"]

            subtitle_clip = (
                TextClip(text, fontsize=24, color="white", bg_color="black")
                .set_position(("center", 0.85), relative=True)
                .set_duration(end_time - start_time)
                .set_start(start_time)
            )
            subtitle_clips.append(subtitle_clip)

        subtitled_video = CompositeVideoClip([video] + subtitle_clips)

        temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

        logging.info(f"[WRITING_FINAL_VIDEO]: {unique_uuid}")

        subtitled_video.write_videofile(
            temp_videofile_path,
            codec="libx264",
            bitrate="1500k",
            threads=os.environ.get("PROCESS_THREADS"),
            preset="faster",
            audio_bitrate="128k",
            audio_fps=44100,
            write_logfile=False,
            logger=None,
        )

        output_video_local_path = os.path.join(
            temp_dir, "output" + os.path.splitext(input_video_file_name)[1]
        )

        cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audio_file)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_local_path)}" -loglevel error'
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

        if not run_locally:
            metrics = 0
        else:
            metrics = None

        shutil.copyfile(temp_videofile_path, output_video_local_path)

        video.close()

        if run_locally:
            # Extract directory and base filename from the local file path
            original_dir = os.path.dirname(input_video_url)
            edited_dir = os.path.join(
                original_dir, "edited"
            )  # Path for the /edited subfolder
            os.makedirs(
                edited_dir, exist_ok=True
            )  # Create the /edited subfolder if it doesn't exist

            original_filename = os.path.basename(input_video_url)
            base_filename, file_extension = os.path.splitext(original_filename)

            # Create the new filename with '_edited' and unique_uuid appended
            new_filename = f"{base_filename}_{unique_uuid}_edited{file_extension}"

            # Create the new file path in the /edited subdirectory
            local_save_path = os.path.join(edited_dir, new_filename)

            shutil.copyfile(output_video_local_path, local_save_path)
            logging.info(f"[SAVED_LOCALLY]: {local_save_path}")

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

            return local_save_path, unique_uuid, metrics

        else:
            if run_bulk:
                file_path = output_video_local_path
            else:
                # S3 uploading logic
                output_video_s3_path = (
                    f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
                )

                logging.info(f"[UPLOADING_TO_S3]: {unique_uuid}")
                presignedUrl = upload_to_s3(
                    output_video_local_path, output_video_s3_path, userId
                )

                file_path = presignedUrl

            # if os.path.exists(temp_dir):
            #     shutil.rmtree(temp_dir)

            return file_path, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing video {input_video_url}. Error: {str(e)}")
        raise
