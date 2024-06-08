import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from dotenv import load_dotenv
from utils.retries import retry

load_dotenv()

FAILURE_WEBHOOK_TRIGGERED = False


@retry(attempts=3, delay=5)
def send_email(email, media_url, media_type="Video"):
    try:
        # Try sending via API first
        url = "https://app.loops.so/api/v1/transactional"
        token = os.environ.get("LOOPS_API_TOKEN")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",  # Correctly prefixing with "Bearer "
        }
        payload = {
            "transactionalId": "clo01eqxa00hbmj0obnmgn03n",
            "email": email,
            "dataVariables": {
                "download_link": media_url,
                "media_type": media_type,
                "dashboard_link": f"https://app.snapy.ai/{media_type.lower()}-silence-remover",
            },
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises an exception for non-200 status codes
        logging.info(f"[API_EMAIL_SENT] to {email}")

    except Exception as e:
        logging.warning(
            f"API failed for {email}. Error: {str(e)}. Falling back to SMTP."
        )

        # Falling back to SMTP
        sender = os.environ.get("email_sender")
        password = os.environ.get("email_password")
        receiver = email
        alias = os.environ.get("email_alias")

        subject = f"Your {media_type} is Ready! 🎉 (Expires in 1 Day)"

        # Email body with HTML
        body = f"""
        <html>
            <body>                
                <p>Thank you for using Snapy! Your {media_type} has been processed successfully. You can:</p>
                
                <ul>
                    <li>Download your file from the Jobs section: https://app.snapy.ai/{media_type.lower()}-silence-remover</li>
                    <li> or download from this link: <a href="{media_url}">Download</a></li>
                </ul>
                
                <p>If you have any questions, feel free to reach out to our <a href="mailto:{sender}">support team</a>.</p>
                
                <p>Warm Regards,</p>
                <p>Snapy Team</p>
            </body>
        </html>
        """

        message = MIMEMultipart("alternative")
        message["From"] = f"Media @ Snapy <{alias}>"
        message["To"] = email
        message["Subject"] = subject

        # Convert the body from string to MIMEText object
        mime_body = MIMEText(body, "html")

        # Attach the MIMEText object to the message
        message.attach(mime_body)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, receiver, message.as_string())
            logging.info(f"[SMTP_EMAIL_SENT] to {email}")


@retry(attempts=3, delay=5)
def trigger_webhook(
    unique_uuid,
    output_video_s3_url,
    original_video_url,
    metrics=None,
    error_message=None,
):
    try:
        webhook_url = f'{os.environ.get("NEXT_APP_URL")}/api/vsr-webhook'
        payload = {
            "uuid": unique_uuid,
            "output_video_url": output_video_s3_url,
            "input_video": original_video_url,  # Adding the original video URL to the payload
            "metrics": metrics,
        }
        if error_message:
            payload["error_message"] = error_message
        headers = {"Content-Type": "application/json"}
        response = requests.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()
        logging.info(f"[WEBHOOK_TRIGGERED]: {unique_uuid}")
    except requests.RequestException as e:
        logging.error(f"Webhook trigger failed for UUID {unique_uuid}. Error: {str(e)}")


def send_failure_webhook(error_message, unique_uuid):
    global FAILURE_WEBHOOK_TRIGGERED

    # If the webhook has already been triggered, just return
    if FAILURE_WEBHOOK_TRIGGERED:
        return

    webhook_url = f'{os.environ.get("NEXT_APP_URL")}/api/vsr-webhook'
    payload = {
        "error_message": error_message,
        "uuid": unique_uuid,
    }
    headers = {"Content-Type": "application/json"}
    try:
        logging.info(f"[ERROR_WEBHOOK_TRIGGERED]: {payload}")
        response = requests.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()

        # After successfully sending the webhook, set the flag to True
        FAILURE_WEBHOOK_TRIGGERED = True

    except requests.RequestException as e:
        logging.error(f"Error webhook trigger failed. Error: {str(e)}")
