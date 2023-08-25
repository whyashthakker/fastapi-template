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


@retry(attempts=3, delay=5)
def send_email(email, video_url):
    try:
        sender = os.environ.get("email_sender")
        password = os.environ.get("email_password")
        receiver = email

        subject = "Your processed video is ready!"

        # Email body with HTML
        body = f"""
        <html>
            <body>
                <h2>🎉 Your Processed Video is Ready! 🎉</h2>
                
                <p>Thank you for using VideoSilenceRemover! Your video has been processed successfully. You can:</p>
                
                <ul>
                    <li><a href="{video_url}">Download your video</a></li>
                    <li>Check the job status and download from your <a href="https://app.videosilenceremover.com/dashboard">dashboard</a></li>
                    <li>Want to process another video? <a href="https://app.videosilenceremover.com/video-silence-remover">Upload another video</a></li>
                </ul>
                
                <p>If you have any questions, feel free to reach out to our <a href="mailto:support@videosilenceremover.com">support team</a>.</p>
                
                <p>Warm Regards,</p>
                <p>VideoSilenceRemover Team</p>
            </body>
        </html>
        """

        message = MIMEMultipart("alternative")
        message["From"] = sender
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
            logging.info(f"[EMAIL_SENT]")
    except smtplib.SMTPException as e:
        logging.error(f"Error sending email to {email}. Error: {str(e)}")
        raise


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


@retry(attempts=3, delay=5)
def send_failure_webhook(error_message):
    webhook_url = f'{os.environ.get("NEXT_APP_URL")}/api/vsr-webhook'
    payload = {"error_message": error_message}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error webhook trigger failed. Error: {str(e)}")
