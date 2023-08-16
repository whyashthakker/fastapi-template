web: uvicorn app:app --host 0.0.0.0 --port $PORT
worker: celery -A celery_config.celery_app worker --loglevel=info --concurrency=1 -Q video_processing
