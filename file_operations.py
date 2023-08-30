import os
import logging
from uuid import uuid4
import requests
import re
from utils.retries import retry

retry(attempts=3, delay=5)


def download_file(url, dest_path):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        logging.info("[FILE_DOWNLOADED]")
    except requests.RequestException as e:
        logging.error(f"Error downloading file from {url}. Error: {str(e)}")
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
