import time
from functools import wraps
import logging


def retry(attempts=3, delay=5, allowed_exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    logging.warning(
                        f"Attempt {attempt+1}/{attempts} failed with error: {str(e)}. Retrying in {delay} seconds..."
                    )
                    if attempt < attempts - 1:  # no delay for the last attempt
                        time.sleep(delay)
                    else:
                        logging.error(f"All {attempts} attempts failed. Giving up.")
                        raise

        return wrapper

    return decorator
