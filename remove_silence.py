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

from generate_xml import generate_premiere_xml

from background_noise import denoise_audio_spectral_subtraction

# from background_noise import clean_background_noise

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
    remove_background_noise=False,
    generate_xml=False,
    run_locally=False,
    run_bulk=False,
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

        audio = video.audio
        audio_file = os.path.join(temp_dir, "temp_audio.wav")

        audio.write_audiofile(audio_file, logger=None)

        if remove_background_noise:
            denoised_audio_file = denoise_audio_spectral_subtraction(audio_file)
            audio_segment = AudioSegment.from_file(denoised_audio_file)
        else:
            audio_segment = AudioSegment.from_file(audio_file)

        # silence_threshold = compute_dynamic_silence_threshold(audio_file)

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

            if generate_xml:
                xml_output_path = os.path.join(temp_dir, f"{unique_uuid}_cuts.xml")
                generate_premiere_xml(
                    sequence_name=f"{unique_uuid}_sequence",
                    video_file_name=input_video_file_name,
                    video_file_path=unique_video_local_path,
                    video_duration=video.duration,
                    nonsilent_ranges=nonsilent_ranges,
                    output_path=xml_output_path,
                    width=video.size[0],
                    height=video.size[1],
                )

                if run_locally:
                    original_dir = os.path.dirname(input_video_url)
                    local_save_path = os.path.join(
                        original_dir, f"{unique_uuid}_cuts.xml"
                    )
                    shutil.copyfile(xml_output_path, local_save_path)
                    logging.info(f"[SAVED_LOCALLY]: {local_save_path}")
                else:
                    xml_s3_path = f"{unique_uuid}_cuts.xml"
                    logging.info(f"[UPLOADING_XML_TO_S3]: {unique_uuid}")
                    presignedUrl = upload_to_s3(xml_output_path, xml_s3_path, userId)

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

                return (
                    local_save_path if run_locally else presignedUrl,
                    unique_uuid,
                    None,
                )

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
                and original_duration * 0.95 > final_duration
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

        if not run_locally:
            metrics = compute_video_metrics(video, final_video, nonsilent_ranges)

        else:
            metrics = None

        audio_with_fps = final_video.audio.set_fps(video.audio.fps)

        temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")

        audio_with_fps.write_audiofile(temp_audiofile_path, logger=None)

        output_video_local_path = os.path.join(
            temp_dir,
            f"output_{unique_uuid}" + os.path.splitext(input_video_file_name)[1],
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

            # if os.path.exists(temp_dir):
            #     shutil.rmtree(temp_dir)

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

        # output_video_s3_path = (
        #     f"{unique_uuid}_output{os.path.splitext(input_video_file_name)[1]}"
        # )

        # # original_video_s3_path = (
        # #     f"{unique_uuid}_original{os.path.splitext(input_video_file_name)[1]}"
        # # )

        # # upload_to_s3(
        # #     unique_video_local_path, original_video_s3_path, userId, folder="original"
        # # )

        # logging.info(f"[UPLOADING_TO_S3]: {unique_uuid}")

        # presignedUrl = upload_to_s3(
        #     output_video_local_path, output_video_s3_path, userId
        # )

        # if os.path.exists(temp_dir):
        #     shutil.rmtree(temp_dir)

        # return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error processing video {input_video_url}. Error: {str(e)}")
        raise
