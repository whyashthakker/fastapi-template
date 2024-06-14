import os
import logging
import shutil
from dotenv import load_dotenv
from s3_operations import upload_to_s3
from utils.safeprocess import safe_process
from utils.metrics import compute_audio_metrics
import replicate

# Load the environment variables
load_dotenv()


@safe_process
def generate_music(
    temp_dir,
    text_prompt,
    unique_uuid,
    userId=None,
    run_locally=False,
    run_bulk_locally=False,
):
    try:
        logging.info(f"[AI_MUSIC_GENERATION_STARTED]: {unique_uuid}.")

        output_filename = f"output.wav"
        output_audio_local_path = os.path.join(temp_dir, output_filename)

        # Use Replicate API to generate music
        output = replicate.run(
            "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb",
            input={"prompt": text_prompt},
        )

        # Save the generated audio to a local file
        with open(output_audio_local_path, "wb") as f:
            f.write(output)

        logging.info(f"[AUDIO_EXPORTED]: {unique_uuid}.")

        output_audio_s3_path = f"{unique_uuid}_output.wav"

        presignedUrl = upload_to_s3(
            output_audio_local_path, output_audio_s3_path, userId
        )

        logging.info(f"[AUDIO_UPLOADED]: {unique_uuid}.")

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        # Compute metrics for the generated audio
        # metrics = compute_audio_metrics(output_audio_local_path)
        metrics = 0

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        logging.error(f"Error generating AI music. Error: {str(e)}")
        raise
