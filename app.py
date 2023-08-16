from __future__ import print_function

# Standard libraries
import os
import tempfile
import shutil
import logging
from uuid import uuid4
from typing import Optional
from celery import Celery

# Third-party libraries

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

# Local libraries
from remove_silence import *
from file_operations import *
from communication import *
from video_processing import process_video

# Initialize FastAPI app
app = FastAPI()


class VideoItem(BaseModel):
    input_video: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300


class AudioItem(BaseModel):
    input_audio: str
    email: str
    silence_threshold: Optional[float] = -36
    min_silence_duration: Optional[int] = 300
    padding: Optional[int] = 300


# 4. FastAPI Routes 1
@app.post("/remove-silence/")
async def remove_silence_route(item: VideoItem):
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
        process_video.apply_async(
            (
                temp_dir,
                input_video_url,
                email,
                unique_uuid,
                silence_threshold,
                min_silence_duration,
                padding,
            )
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


@app.post("/audio-silence/")
async def audio_silence_removal(item: AudioItem, background_tasks: BackgroundTasks):
    return "Removing silence from audio."
