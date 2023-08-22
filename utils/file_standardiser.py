import ffmpeg
import os


def detect_problematic_video(video_path):
    """
    Detect if the video is from a problematic source or has certain characteristics.

    Args:
    - video_path (str): Path to the video.

    Returns:
    - bool: True if the video is problematic, False otherwise.
    """
    # Placeholder logic: for instance, checking the video's codec or other metadata.
    # This is just a dummy check and should be replaced with the actual detection logic.
    video_info = ffmpeg.probe(video_path)
    codec_name = video_info["streams"][0]["codec_name"]
    if codec_name in ["some_problematic_codec"]:
        return True
    return False


def convert_to_standard_format(video_path, output_dir):
    """
    Convert the video to a standard format (.mp4 with libx264 video codec and aac audio codec).

    Args:
    - video_path (str): Path to the input video.
    - output_dir (str): Directory to save the converted video.

    Returns:
    - str: Path to the converted video.
    """

    converted_video_path = os.path.join(output_dir, "converted_video.mp4")
    ffmpeg.input(video_path).output(
        converted_video_path, vcodec="libx264", acodec="aac"
    ).run()

    return converted_video_path
