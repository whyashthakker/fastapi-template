import boto3
import logging
from dotenv import load_dotenv
import os
from utils.retries import retry
from datetime import datetime

# Load the environment variables
load_dotenv()

# Set the S3 credentials and config from environment variables
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
REGION_NAME = os.environ.get("AWS_REGION_NAME")
EXPIRATION = 86400

s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION_NAME,
)


def determine_content_type(file_path):
    if file_path.endswith(".wav"):
        return "audio/wav"
    elif file_path.endswith(".mp3"):
        return "audio/mpeg"
    elif file_path.endswith(".zip"):
        return "application/zip"
    else:
        return "video/mp4"


@retry(attempts=3, delay=5)
def upload_to_s3(local_path, s3_path, userId, folder="trimmed"):
    try:
        # Check if file exists
        if not os.path.exists(local_path):
            logging.error(f"File does not exist at {local_path}")
            raise FileNotFoundError(f"File not found at {local_path}")

        # Generate today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")

        content_type = determine_content_type(local_path)

        extra_args = {"ContentType": content_type}

        # Modify s3_path to include the userId, today's date, and the specified folder
        s3_path = f"{userId}/{today}/{folder}/{s3_path}"

        s3.upload_file(local_path, BUCKET_NAME, s3_path, ExtraArgs=extra_args)

        # Generate a pre-signed URL for the uploaded file
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_path},
            ExpiresIn=EXPIRATION,
        )

        logging.info("[UPLOADED_TO_S3]")

        return presigned_url

    except Exception as e:
        logging.warning(f"Failed to upload to S3. Error: {str(e)}")
        raise
