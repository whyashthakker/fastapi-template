from functools import wraps
from communication import send_failure_webhook
import logging


def safe_process(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            function_name = func.__name__
            error_msg = str(e)
            logging.error(f"Error occurred in function {function_name}: {error_msg}")
            # Check if the error message does not indicate a webhook failure
            if "webhook" not in error_msg.lower():
                send_failure_webhook(error_msg)
            raise

    return wrapper
