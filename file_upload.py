import boto3
import os

# Set the S3 credentials and config from environment variables
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.environ.get("BUCKET_NAME")
REGION_NAME = os.environ.get("REGION_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION_NAME,
)

BUCKET_NAME = "videosil"

file_upload = s3.Bucket(BUCKET_NAME).upload_file(
    "requirements.txt", "videofiles/requirements.txt"
)

delete_file = s3.Object(BUCKET_NAME, "videofiles/requirements.txt").delete()

print(file_upload)
