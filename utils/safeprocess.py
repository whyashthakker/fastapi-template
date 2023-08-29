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

            # Extract unique_uuid from the function arguments.
            # Assuming unique_uuid is the third argument of the wrapped function:
            unique_uuid = args[2]

            # Check for specific known errors and replace with user-friendly message
            if str(e) == "nonsilent_ranges is None or empty.":
                friendly_error = "The video does not contain any detectable audio."
            else:
                friendly_error = "Something went wrong."

            logging.error(
                f"Error in function {function_name}: {str(e)}"
            )  # Log the technical error for debugging

            # Send a failure webhook if the error is not related to the webhook itself
            if "webhook" not in str(e).lower():
                send_failure_webhook(friendly_error, unique_uuid)

            raise

    return wrapper
