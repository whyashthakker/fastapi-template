import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, istft


def denoise_audio_spectral_subtraction(
    audio_file, noise_duration=0.5, amplification_factor=1.9
):
    # 1. Read in the audio file
    rate, data = wavfile.read(audio_file)
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
    _, cleaned_data = istft(Zxx_denoised, fs=rate, nperseg=nperseg, noverlap=noverlap)

    # Adjust the magnitude
    cleaned_data = cleaned_data * amplification_factor
    cleaned_data = np.clip(
        cleaned_data, -32768, 32767
    )  # Clip to prevent values outside int16 range

    # Write out the processed audio
    cleaned_audio_file = audio_file.replace(".wav", "_spectral_subtracted.wav")
    wavfile.write(cleaned_audio_file, rate, cleaned_data.astype(np.int16))

    return cleaned_audio_file
