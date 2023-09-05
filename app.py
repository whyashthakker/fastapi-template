from __future__ import print_function

# Standard libraries
import os
import tempfile
import shutil
import logging
from uuid import uuid4
from typing import Optional
from dotenv import load_dotenv

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


class AudioItem(BaseModel):
    input_audio: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300
    userId: Optional[str] = None
    available_credits: Optional[float] = None


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

    if input_video_url is None:
        logging.error("input_video_url is None.")
        raise HTTPException(status_code=400, detail="Please share a valid video URL.")

    duration = get_media_duration(input_video_url)
    cost = calculate_cost(duration)
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
    temp_dir = tempfile.mkdtemp()

    try:
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
            )
        )
    except Exception as e:
        logging.error(f"Failed to initiate video processing. Error: {str(e)}")
        trigger_webhook(unique_uuid, None, None, error_message=str(e))
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
        "video_duration": duration,
        "cost": cost,
    }


@app.post("/audio-silence/")
async def audio_silence_removal(item: AudioItem, background_tasks: BackgroundTasks):
    input_audio_url = item.input_audio
    email = item.email
    silence_threshold = item.silence_threshold
    min_silence_duration = item.min_silence_duration
    padding = item.padding
    userId = item.userId
    available_credits = item.available_credits

    if input_audio_url is None:
        logging.error("input_audio_url is None.")
        trigger_webhook(None, error_message="Please share a valid audio URL.")
        return {
            "status": "Failed to initiate audio processing. Please share a valid audio URL.",
            "error_message": "Please share a valid audio URL.",
        }

    duration = get_media_duration(input_audio_url)
    cost = calculate_cost(duration)
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
                email,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
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
