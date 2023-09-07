import soundfile as sf
import noisereduce as nr
import logging
import time
import gc
import shutil

# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def clean_background_noise(input_path, output_path, sr=None, stationary=True):
    # Start the timer
    start_time = time.time()

    # Log the start of the processing
    logging.info(f"Starting background noise cleaning for {input_path}.")

    try:
        # Check the duration of the audio without loading the entire file
        with sf.SoundFile(input_path) as sound_file:
            duration = len(sound_file) / sound_file.samplerate
            channels = sound_file.channels
            rate = sr if sr else sound_file.samplerate

        # If the audio duration is very short, handle it differently
        if duration < 0.1:  # 0.1 seconds as an arbitrary threshold
            logging.warning(
                f"Audio clip {input_path} is too short ({duration} seconds). Skipping noise reduction."
            )
            shutil.copy(input_path, output_path)
            return output_path

        # Open the output file once
        out_file = sf.SoundFile(output_path, "w", samplerate=rate, channels=channels)

        # Load the audio data in chunks, process, and then write in chunks
        block_size = 1024 * 10  # or any appropriate size
        with sf.SoundFile(input_path) as sound_file:
            for block in sound_file.blocks(blocksize=block_size):
                # Apply noise reduction
                reduced_noise = nr.reduce_noise(
                    y=block, sr=rate, stationary=stationary, n_jobs=-1
                )
                # Save the noise reduced audio to the output path
                out_file.write(reduced_noise)

        # Close the output file
        out_file.close()

        # Explicit garbage collection
        gc.collect()

    except Exception as e:
        logging.error(f"Error during noise reduction for {input_path}. Error: {str(e)}")
        # Copy the input to the output path to return the same audio
        shutil.copy(input_path, output_path)

    # Calculate and log the time taken
    elapsed_time = time.time() - start_time
    logging.info(
        f"Finished background noise cleaning for {input_path} in {elapsed_time:.2f} seconds."
    )

    return output_path
