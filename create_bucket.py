import boto3

client = boto3.client("s3")
s3 = boto3.resource("s3")

create_bucket = s3.create_bucket(
    Bucket="vsr-bucket-12345",
    CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
)

print(create_bucket)

list_bucket = client.list_buckets()

for bucket in list_bucket["Buckets"]:
    print(bucket["Name"])
