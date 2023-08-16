from celery import Celery
from kombu import Exchange, Queue
import os
from dotenv import load_dotenv

load_dotenv()

# user = os.environ.get("RABBITMQ_DEFAULT_USER")
# password = os.environ.get("RABBITMQ_DEFAULT_PASS")
# host = "railway-rabbitmq-production-1ffa.up.railway.app"
# port = 5672
# vhost = "/"

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
)


def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=["video_processing"],
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
