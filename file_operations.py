import os
import logging
from uuid import uuid4
import requests


def download_file(url, dest_path):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        logging.info(f"Downloading file from {url} to {dest_path}")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
    except requests.RequestException as e:
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
