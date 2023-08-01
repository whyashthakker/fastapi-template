from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import tempfile
import shutil
import subprocess
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

app = FastAPI()

class VideoItem(BaseModel):
    input_video: str
    output_video: str

def remove_silence(input_video, output_video, silence_threshold=-35, min_silence_duration=300, padding=200, progress_callback=None):
    temp_dir = tempfile.mkdtemp()
    os.environ['MOVIEPY_TEMP_FOLDER'] = temp_dir

    video = VideoFileClip(input_video)
    audio = video.audio

    audio_file = os.path.join(temp_dir, "temp_audio.wav")
    audio.write_audiofile(audio_file)
    audio_segment = AudioSegment.from_file(audio_file)

    nonsilent_ranges = detect_nonsilent(audio_segment, min_silence_len=min_silence_duration, silence_thresh=silence_threshold)
    nonsilent_ranges = [(start - padding, end + padding) for start, end in nonsilent_ranges]

    non_silent_subclips = [video.subclip(max(start / 1000, 0), min(end / 1000, video.duration)) for start, end in nonsilent_ranges]

    final_video = concatenate_videoclips(non_silent_subclips)

    temp_audiofile_path = os.path.join(temp_dir, "temp_audiofile.mp3")
    temp_videofile_path = os.path.join(temp_dir, "temp_videofile.mp4")

    final_video.write_videofile(temp_videofile_path, codec="libx264", audio=False)

    audio_with_fps = final_video.audio.set_fps(video.audio.fps)
    audio_with_fps.write_audiofile(temp_audiofile_path)

    # Use the same extension as the input video for the output video
    output_ext = os.path.splitext(input_video)[1]
    output_video_base, _ = os.path.splitext(output_video)
    output_video_with_ext = f"{output_video_base}{output_ext}"

    cmd = f'ffmpeg -y -i "{os.path.normpath(temp_videofile_path)}" -i "{os.path.normpath(temp_audiofile_path)}" -c:v copy -c:a aac -strict experimental -shortest "{os.path.normpath(output_video_with_ext)}"'
    subprocess.run(cmd, shell=True, check=True)

    video.close()

    shutil.rmtree(temp_dir)

@app.post("/remove-silence/")
async def remove_silence_route(item: VideoItem):
    input_video = item.input_video
    output_video = item.output_video
    
    # Extract the file extension from the input video
    file_extension = os.path.splitext(input_video)[1]
    
    # Append the file extension to the output video
    output_video_with_ext = output_video + file_extension

    try:
        remove_silence(input_video, output_video_with_ext)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
