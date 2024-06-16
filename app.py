from __future__ import print_function

# Standard libraries
import os
import tempfile
import shutil
import logging
from uuid import uuid4
from typing import Optional
from dotenv import load_dotenv
from time import sleep

# Third-party libraries

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from fastapi import HTTPException, Header, Depends

# Local libraries
from remove_silence import *
from file_operations import *
from communication import *
from audio_processing import process_audio
from video_processing import process_video
from file_duration import *

# Initialize FastAPI app
app = FastAPI()

# Load environment variables
load_dotenv()


class VideoItem(BaseModel):
    input_video: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300
    userId: Optional[str] = None
    available_credits: Optional[float] = None
    remove_background_noise: Optional[bool] = False
    run_locally: Optional[bool] = False
    run_bulk_locally: Optional[bool] = False
    task_type: Optional[str] = "remove_silence_video"
    generate_srt: Optional[bool] = False
    run_bulk: Optional[bool] = False


class AudioItem(BaseModel):
    input_audio: Optional[str] = None
    input_audio_urls: Optional[list] = None
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300
    userId: Optional[str] = None
    available_credits: Optional[float] = None
    remove_background_noise: Optional[bool] = False
    run_locally: Optional[bool] = False
    run_bulk_locally: Optional[bool] = False
    task_type: Optional[str] = "remove_silence_audio"
    loop_count: Optional[int] = None
    loop_duration: Optional[int] = None
    output_format: Optional[str] = "wav"
    noise_duration: Optional[float] = 0
    amplification_factor: Optional[float] = 1.0
    text_prompt: Optional[str] = None
    speed_factor: Optional[float] = 1.0
    background_audio_url: Optional[str] = None
    gain_during_overlay: Optional[float] = -10
    run_bulk: Optional[bool] = False


class VideoDurationItem(BaseModel):
    video_url: str


def verify_authorization_key(authorization_key: str = Header(...)):
    CONFIGURED_KEYS = os.environ.get("AUTH_KEY")
    if authorization_key not in CONFIGURED_KEYS:
        raise HTTPException(status_code=403, detail="Not authorized")
    return authorization_key


# 4. FastAPI Route
@app.post("/remove-silence/")
async def remove_silence_route(
    item: VideoItem, authorization: str = Depends(verify_authorization_key)
):
    input_video_url = item.input_video
    email = item.email
    silence_threshold = item.silence_threshold
    min_silence_duration = item.min_silence_duration
    padding = item.padding
    userId = item.userId
    available_credits = item.available_credits
    remove_background_noise = item.remove_background_noise
    run_locally = item.run_locally
    run_bulk_locally = item.run_bulk_locally
    duration = 0
    cost = 0
    task_type = item.task_type
    run_bulk = item.run_bulk

    if input_video_url is None:
        logging.error("input_video_url is None.")
        raise HTTPException(status_code=400, detail="Please share a valid video URL.")

    if not (run_locally or run_bulk_locally):
        duration = get_media_duration(input_video_url)
        cost = calculate_cost(duration, task_type=task_type)
        if available_credits < cost:
            raise HTTPException(
                status_code=403,
                detail={
                    "status": "Failed to initiate video processing.",
                    "error_message": "Insufficient credits for the video duration.",
                    "video_duration": duration,
                    "cost": cost,
                },
            )

    unique_uuid = str(uuid4())
    # temp_dir = tempfile.mkdtemp()

    if run_bulk_locally:
        all_files = look_for_mp4_files_locally(
            input_video_url
        )  # Ensure this gets the correct path
        for file in all_files:
            sleep(5)
            unique_uuid_for_file = str(uuid4())  # Generate a unique UUID for each file
            try:
                temp_dir = (
                    tempfile.mkdtemp()
                )  # Create a new temp directory for each file
                process_video.apply_async(
                    (
                        temp_dir,
                        file,  # Use the current file in the loop
                        email,
                        unique_uuid_for_file,
                        silence_threshold,
                        min_silence_duration,
                        padding,
                        userId,
                        remove_background_noise,
                        True,  # run_locally should be True here
                        task_type,
                        run_bulk,
                    )
                )
            except Exception as e:
                logging.error(
                    f"Failed to initiate video processing for {file}. Error: {str(e)}"
                )
                trigger_webhook(unique_uuid, None, None, error_message=str(e))
                # Consider how to handle partial failures
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
    else:
        # Process a single file
        try:
            temp_dir = tempfile.mkdtemp()

            process_video.apply_async(
                (
                    temp_dir,
                    input_video_url,
                    email,
                    unique_uuid,
                    silence_threshold,
                    min_silence_duration,
                    padding,
                    userId,
                    remove_background_noise,
                    run_locally,
                    task_type,
                    run_bulk,
                )
            )
        except Exception as e:
            logging.error(f"Failed to initiate video processing. Error: {str(e)}")
            trigger_webhook(unique_uuid, None, None, error_message=str(e))
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    return {
        "status": "Video processing started. You will be notified by email once it's done.",
        "request_id": unique_uuid,
        "video_duration": duration,
        "cost": cost,
    }


@app.post("/audio-silence/")
async def audio_silence_removal(item: AudioItem, background_tasks: BackgroundTasks):
    input_audio_url = item.input_audio
    input_audio_urls = item.input_audio_urls
    email = item.email
    silence_threshold = item.silence_threshold
    min_silence_duration = item.min_silence_duration
    padding = item.padding
    userId = item.userId
    available_credits = item.available_credits
    remove_background_noise = item.remove_background_noise
    task_type = item.task_type
    run_locally = item.run_locally
    run_bulk_locally = item.run_bulk_locally
    loop_count = item.loop_count
    loop_duration = item.loop_duration
    output_format = item.output_format
    noise_duration = item.noise_duration
    amplification_factor = item.amplification_factor
    text_prompt = item.text_prompt
    speed_factor = item.speed_factor
    background_audio_url = item.background_audio_url
    gain_during_overlay = item.gain_during_overlay
    run_bulk = item.run_bulk

    if input_audio_url is None and input_audio_urls is None:
        logging.error("Both input_audio_url and input_audio_urls are None.")
        trigger_webhook(
            None,
            error_message="Please provide either input_audio_url or input_audio_urls.",
        )
        return {
            "status": "Failed to initiate audio processing. Please provide either input_audio_url or input_audio_urls.",
            "error_message": "Please provide either input_audio_url or input_audio_urls.",
        }

    if input_audio_urls:
        duration = get_total_duration(input_audio_urls)
    else:
        duration = get_media_duration(input_audio_url)

    if input_audio_urls:
        duration = get_total_duration(input_audio_urls)
    else:
        duration = get_media_duration(input_audio_url)

    cost = calculate_cost(duration, task_type=task_type)

    if available_credits < cost:
        return {
            "status": "Failed to initiate audio processing.",
            "error_message": "Insufficient credits for the audio duration.",
            "audio_duration": duration,
            "cost": cost,
        }

    unique_uuid = str(uuid4())
    temp_dir = tempfile.mkdtemp()

    try:
        process_audio.apply_async(
            (
                temp_dir,
                input_audio_url,
                input_audio_urls,
                email,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
                userId,
                remove_background_noise,
                run_locally,
                run_bulk_locally,
                task_type,
                loop_count,
                loop_duration,
                output_format,
                noise_duration,
                amplification_factor,
                text_prompt,
                speed_factor,
                background_audio_url,
                gain_during_overlay,
                run_bulk,
            )
        )
    except Exception as e:
        logging.error(f"Failed to initiate audio processing. Error: {str(e)}")
        trigger_webhook(unique_uuid, None, error_message=str(e))
        return {
            "status": "Failed to initiate audio processing.",
            "error_message": str(e),
        }
    finally:
        # Cleanup temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    return {
        "status": "Audio processing started. You will be notified by email once it's done.",
        "request_id": unique_uuid,
        "audio_duration": duration,
        "cost": cost,
    }
