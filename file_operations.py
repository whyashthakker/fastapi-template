import os
import logging
from uuid import uuid4
import requests
import re
from utils.retries import retry
import shutil

retry(attempts=3, delay=5)


def download_file(url, dest_path, run_locally=False):
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        if run_locally:
            # Assuming 'url' is a path to the local file
            if os.path.exists(url):
                shutil.copyfile(url, dest_path)
            else:
                logging.error(f"Local file {url} does not exist.")
                raise FileNotFoundError(f"Local file {url} does not exist.")
        else:
            r = requests.get(url, stream=True)
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

        logging.info("[FILE_DOWNLOADED]")
    except requests.RequestException as e:
        logging.error(f"Error downloading file from {url}. Error: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error in file operation: {str(e)}")
        raise


def get_unique_filename(original_name: str) -> str:
    try:
        unique_filename = f"{uuid4()}{os.path.splitext(original_name)[1]}"
        logging.info("[FILE_RENAMED]")
        return unique_filename
    except Exception as e:
        logging.error(
            f"Error generating unique filename for {original_name}. Error: {str(e)}"
        )
        raise


def sanitize_filename(filename: str) -> str:
    # Remove non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s-]", "", filename)
    # Replace all runs of whitespace with a single dash #
    s = re.sub(r"\s+", "-", s)
    return s


def look_for_mp4_files_locally(directory: str) -> list:
    mp4_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".mp4"):
                    mp4_files.append(os.path.join(root, file))
    except Exception as e:
        logging.error(f"Error looking for mp4 files in {directory}. Error: {str(e)}")
        raise

    logging.info(f"Found {len(mp4_files)} mp4 files in {directory}.")

    return mp4_files
