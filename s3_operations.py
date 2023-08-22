import boto3
import logging
import time
from dotenv import load_dotenv
import os
from utils.retries import retry

# Load the environment variables
load_dotenv()

# Set the S3 credentials and config from environment variables
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
REGION_NAME = os.environ.get("AWS_REGION_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION_NAME,
)


@retry(attempts=3, delay=5)
def upload_to_s3(local_path, s3_path):
    try:
        logging.info("Uploading to S3...")
        logging.info(f"Local path: {local_path}")
        logging.info(f"S3 path: {s3_path}")
        s3.upload_file(local_path, BUCKET_NAME, s3_path)
        logging.info("Uploaded to S3 successfully")
    except Exception as e:
        logging.warning(f"Failed to upload to S3. Error: {str(e)}")
        raise
