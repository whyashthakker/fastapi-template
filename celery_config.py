from celery import Celery
from kombu import Exchange, Queue
import os
from dotenv import load_dotenv

load_dotenv()

BROKER_URL = os.environ.get("REDIS_URL") or os.environ.get("BROKER_URL")
RESULT_BACKEND = "rpc://"
TASK_SERIALIZER = "json"
RESULT_SERIALIZER = "json"
ACCEPT_CONTENT = ["json"]
BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_QUEUES = (
    Queue(
        "video_processing", Exchange("video_processing"), routing_key="video_processing"
    ),
    Queue(
        "audio_processing", Exchange("audio_processing"), routing_key="audio_processing"
    ),
)


def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=[
            "video_processing",
            "audio_processing",
        ],  # Updated to include audio_processing
    )
    celery.conf.update(
        task_serializer=TASK_SERIALIZER,
        result_serializer=RESULT_SERIALIZER,
        accept_content=ACCEPT_CONTENT,
        broker_url=BROKER_URL,
        result_backend=RESULT_BACKEND,
        broker_connection_retry_on_startup=BROKER_CONNECTION_RETRY_ON_STARTUP,
        task_queues=CELERY_QUEUES,
    )
    return celery


celery_app = make_celery()
