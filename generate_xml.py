import xml.etree.ElementTree as ET
from datetime import timedelta


def generate_premiere_xml(
    sequence_name,
    video_file_name,
    video_file_path,
    video_duration,
    nonsilent_ranges,
    output_path,
    width,
    height,
):
    root = ET.Element("xmeml", version="5")
    sequence = ET.SubElement(root, "sequence")
    sequence.set("explodedTracks", "true")
    ET.SubElement(sequence, "name").text = sequence_name
    ET.SubElement(sequence, "duration").text = str(int(video_duration * 60))

    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = "60"
    ET.SubElement(rate, "ntsc").text = "FALSE"

    # Add timecode information
    timecode = ET.SubElement(sequence, "timecode")
    ET.SubElement(timecode, "string").text = "00:00:00:00"
    ET.SubElement(timecode, "displayformat").text = "NDF"
    timecode_rate = ET.SubElement(timecode, "rate")
    ET.SubElement(timecode_rate, "timebase").text = "60"
    ET.SubElement(timecode_rate, "ntsc").text = "FALSE"

    # Add video track
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    format = ET.SubElement(video, "format")
    sample_characteristics = ET.SubElement(format, "samplecharacteristics")
    ET.SubElement(sample_characteristics, "width").text = str(width)
    ET.SubElement(sample_characteristics, "height").text = str(height)
    ET.SubElement(sample_characteristics, "pixelaspectratio").text = "square"
    sample_rate = ET.SubElement(sample_characteristics, "rate")
    ET.SubElement(sample_rate, "timebase").text = "60"
    ET.SubElement(sample_rate, "ntsc").text = "FALSE"

    video_track = ET.SubElement(video, "track")
    clip_index = 1

    for start, end in nonsilent_ranges:
        clip = ET.SubElement(
            video_track, "clipitem", id=f"{video_file_name} {clip_index}"
        )
        ET.SubElement(clip, "name").text = video_file_name
        ET.SubElement(clip, "enabled").text = "TRUE"
        ET.SubElement(clip, "duration").text = str(int(video_duration * 60))
        clip_rate = ET.SubElement(clip, "rate")
        ET.SubElement(clip_rate, "timebase").text = "60"
        ET.SubElement(clip_rate, "ntsc").text = "FALSE"

        start_frame = int(start * 60)
        end_frame = int(end * 60)

        ET.SubElement(clip, "start").text = str(start_frame)
        ET.SubElement(clip, "end").text = str(end_frame)
        ET.SubElement(clip, "in").text = str(start_frame)
        ET.SubElement(clip, "out").text = str(end_frame)

        file = ET.SubElement(
            clip, "file", id=f"{video_file_name}-file-14686428782635475788"
        )
        ET.SubElement(file, "rate").text = str(60)
        ET.SubElement(file, "ntsc").text = "FALSE"
        ET.SubElement(file, "name").text = video_file_name
        ET.SubElement(file, "duration").text = str(int(video_duration * 60))
        ET.SubElement(file, "pathurl").text = f"file:///{video_file_path}"

        timecode = ET.SubElement(file, "timecode")
        ET.SubElement(timecode, "string").text = "00:00:00:00"
        ET.SubElement(timecode, "displayformat").text = "NDF"
        timecode_rate = ET.SubElement(timecode, "rate")
        ET.SubElement(timecode_rate, "timebase").text = "60"
        ET.SubElement(timecode_rate, "ntsc").text = "FALSE"

        media_info = ET.SubElement(file, "media")
        video_info = ET.SubElement(media_info, "video")
        ET.SubElement(video_info, "duration").text = str(int(video_duration * 60))
        video_sample_characteristics = ET.SubElement(
            video_info, "samplecharacteristics"
        )
        ET.SubElement(video_sample_characteristics, "width").text = str(width)
        ET.SubElement(video_sample_characteristics, "height").text = str(height)
        ET.SubElement(video_sample_characteristics, "pixelaspectratio").text = "square"
        audio_info = ET.SubElement(media_info, "audio")
        ET.SubElement(audio_info, "channelcount").text = "2"

        # Add links for video and audio
        ET.SubElement(clip, "compositemode").text = "normal"
        video_link = ET.SubElement(clip, "link")
        ET.SubElement(video_link, "linkclipref").text = (
            f"{video_file_name} {clip_index}"
        )
        ET.SubElement(video_link, "mediatype").text = "video"
        ET.SubElement(video_link, "trackindex").text = "1"
        ET.SubElement(video_link, "clipindex").text = str(clip_index)

        clip_index += 1

    # Add audio track
    audio = ET.SubElement(media, "audio")
    ET.SubElement(audio, "numOutputChannels").text = "2"
    audio_format = ET.SubElement(audio, "format")
    audio_sample_characteristics = ET.SubElement(audio_format, "samplecharacteristics")
    ET.SubElement(audio_sample_characteristics, "depth").text = "16"
    ET.SubElement(audio_sample_characteristics, "samplerate").text = "48000"

    # Add output channels
    outputs = ET.SubElement(audio, "outputs")
    for channel_index in range(1, 3):
        group = ET.SubElement(outputs, "group")
        ET.SubElement(group, "index").text = str(channel_index)
        ET.SubElement(group, "numchannels").text = "1"
        ET.SubElement(group, "downmix").text = "0"
        channel = ET.SubElement(group, "channel")
        ET.SubElement(channel, "index").text = str(channel_index)

    # Add audio tracks
    for track_index in range(1, 3):
        audio_track = ET.SubElement(
            audio,
            "track",
            currentExplodedTrackIndex=str(track_index - 1),
            totalExplodedTrackCount="2",
            premiereTrackType="Stereo",
        )
        ET.SubElement(audio_track, "outputchannelindex").text = str(track_index)

        for clip_index, (start, end) in enumerate(nonsilent_ranges, start=1):
            clip = ET.SubElement(
                audio_track,
                "clipitem",
                id=f"{video_file_name} {track_index * 38 + clip_index}",
                premiereChannelType="stereo",
            )
            ET.SubElement(clip, "name").text = video_file_name
            ET.SubElement(clip, "enabled").text = "TRUE"
            ET.SubElement(clip, "duration").text = str(int(video_duration * 60))
            clip_rate = ET.SubElement(clip, "rate")
            ET.SubElement(clip_rate, "timebase").text = "60"
            ET.SubElement(clip_rate, "ntsc").text = "FALSE"

            start_frame = int(start * 60)
            end_frame = int(end * 60)

            ET.SubElement(clip, "start").text = str(start_frame)
            ET.SubElement(clip, "end").text = str(end_frame)
            ET.SubElement(clip, "in").text = str(start_frame)
            ET.SubElement(clip, "out").text = str(end_frame)

            file = ET.SubElement(
                clip, "file", id=f"{video_file_name}-file-14686428782635475788"
            )
            ET.SubElement(file, "sourcetrack").text = (
                f"<mediatype>audio</mediatype><trackindex>{track_index}</trackindex>"
            )

            video_link = ET.SubElement(clip, "link")
            ET.SubElement(video_link, "linkclipref").text = (
                f"{video_file_name} {clip_index}"
            )
            ET.SubElement(video_link, "mediatype").text = "video"
            ET.SubElement(video_link, "trackindex").text = "1"
            ET.SubElement(video_link, "clipindex").text = str(clip_index)

            audio_link = ET.SubElement(clip, "link")
            ET.SubElement(audio_link, "linkclipref").text = (
                f"{video_file_name} {track_index * 38 + clip_index}"
            )
            ET.SubElement(audio_link, "mediatype").text = "audio"
            ET.SubElement(audio_link, "trackindex").text = str(track_index)
            ET.SubElement(audio_link, "clipindex").text = str(clip_index)
            ET.SubElement(audio_link, "groupindex").text = str(track_index)

    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
