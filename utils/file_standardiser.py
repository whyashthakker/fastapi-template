import ffmpeg
import os
import logging


def detect_problematic_video(video_path):
    video_info = ffmpeg.probe(video_path)
    codec_name = video_info["streams"][0]["codec_name"]
    if codec_name in ["some_problematic_codec"]:
        return True
    return False


def convert_to_standard_format(video_path, output_dir):
    logging.info(f"[CONVERTING_VIDEO]")
    converted_video_path = os.path.join(output_dir, "converted_video.mp4")
    ffmpeg.input(video_path).output(
        converted_video_path, vcodec="libx264", acodec="aac", vf="scale=-1:-1"
    ).global_args("-loglevel", "error").run()

    return converted_video_path
