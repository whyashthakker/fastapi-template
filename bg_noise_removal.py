import os
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, istft
from pydub import AudioSegment
import tempfile
import shutil
from s3_operations import upload_to_s3
from utils.metrics import compute_audio_metrics
from file_operations import *
import logging


def remove_background_noise_from_audio(
    temp_dir,
    input_audio_url,
    unique_uuid,
    noise_duration=0.5,
    amplification_factor=1.9,
    output_format="wav",
    userId=None,
):
    try:
        logging.info(f"[BACKGROUND_NOISE_FUNCTION_STARTED]: {unique_uuid}.")

        original_name = os.path.basename(input_audio_url.split("?")[0])
        original_name = sanitize_filename(original_name)

        _, file_extension = os.path.splitext(original_name)
        if not file_extension:
            original_name += ".wav"

        input_audio_local_path = os.path.join(temp_dir, original_name)
        download_file(input_audio_url, input_audio_local_path)

        # Load the audio file using pydub
        audio_segment = AudioSegment.from_file(input_audio_local_path)

        # Convert the audio to WAV format
        wav_audio_path = os.path.join(temp_dir, "temp_audio.wav")
        audio_segment.export(wav_audio_path, format="wav")

        # Read in the WAV audio file
        rate, data = wavfile.read(wav_audio_path)
        if len(data.shape) == 2:  # Stereo
            data = data.mean(axis=1)

        # Parameters for STFT
        nperseg = 1024
        noverlap = int(nperseg * 0.75)

        # Perform STFT
        f, t, Zxx = stft(data, fs=rate, nperseg=nperseg, noverlap=noverlap)

        # Estimate the noise using the first few frames (assuming they only contain noise)
        noise_frames = int(noise_duration * rate / (nperseg - noverlap))
        noise_estimation = np.abs(Zxx[:, :noise_frames]).mean(axis=1).reshape(-1, 1)

        # Subtract the noise estimate from the magnitude spectrum
        Zxx_magnitude = np.abs(Zxx) - noise_estimation
        Zxx_magnitude = np.maximum(Zxx_magnitude, 0)  # ensure non-negative values

        # Reconstruct the modified spectrum (keep the original phase)
        Zxx_denoised = Zxx_magnitude * np.exp(1j * np.angle(Zxx))

        # Perform inverse STFT
        _, cleaned_data = istft(
            Zxx_denoised, fs=rate, nperseg=nperseg, noverlap=noverlap
        )

        # Adjust the magnitude
        cleaned_data = cleaned_data * amplification_factor
        cleaned_data = np.clip(
            cleaned_data, -32768, 32767
        )  # Clip to prevent values outside int16 range

        # Write out the processed audio
        cleaned_audio_local_path = os.path.join(temp_dir, f"output.{output_format}")
        wavfile.write(cleaned_audio_local_path, rate, cleaned_data.astype(np.int16))

        # Upload the cleaned audio to S3
        output_audio_s3_path = f"{unique_uuid}_output.{output_format}"
        presignedUrl = upload_to_s3(
            cleaned_audio_local_path, output_audio_s3_path, userId
        )

        # Compute metrics for the cleaned audio
        cleaned_audio = AudioSegment.from_wav(cleaned_audio_local_path)
        # metrics = compute_audio_metrics(cleaned_audio)

        metrics = 0

        return presignedUrl, unique_uuid, metrics

    except Exception as e:
        raise ValueError(f"Error processing audio: {str(e)}")

    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
