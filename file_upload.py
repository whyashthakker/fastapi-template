import boto3

client = boto3.client("s3")
s3 = boto3.resource("s3")

bucket_name = "videosil"

file_upload = s3.Bucket(bucket_name).upload_file(
    "requirements.txt", "videofiles/requirements.txt"
)

delete_file = s3.Object(bucket_name, "videofiles/requirements.txt").delete()

print(file_upload)
