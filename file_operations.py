import os
import logging
from uuid import uuid4
import requests
import yt_dlp


def download_video(url, dest_path):
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "outtmpl": dest_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_file(url, dest_path):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Check if the URL is a YouTube link
        if "youtube.com" in url or "youtu.be" in url:
            logging.info(f"Downloading YouTube video from {url} to {dest_path}")
            download_video(url, dest_path)
        else:
            logging.info(f"Downloading file from {url} to {dest_path}")
            r = requests.get(url, stream=True)
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

        logging.info(f"Downloaded file from {url} to {dest_path}")

        logging.info(f"file name is {os.path.basename(dest_path)}")

        logging.info(
            f"list of files in {os.path.dirname(dest_path)} is {os.listdir(os.path.dirname(dest_path))}"
        )
    except Exception as e:
        logging.error(f"Error downloading file from {url}. Error: {str(e)}")
        raise


def get_unique_filename(original_name: str) -> str:
    try:
        unique_filename = f"{uuid4()}{os.path.splitext(original_name)[1]}"
        return unique_filename
    except Exception as e:
        logging.error(
            f"Error generating unique filename for {original_name}. Error: {str(e)}"
        )
        raise
