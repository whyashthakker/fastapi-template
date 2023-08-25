from utils.retries import retry
import logging


@retry(attempts=3, delay=5)
def compute_video_metrics(original_video, final_video, nonsilent_ranges):
    logging.info(f"[COMPUTING_METRICS]")
    original_duration = int(original_video.duration)
    final_duration = int(final_video.duration)
    duration_reduction = original_duration - final_duration

    total_silent_duration_removed = (
        sum([(end - start) for start, end in nonsilent_ranges]) / 1000
    )  # Convert from ms to seconds
    number_of_cuts_made = len(nonsilent_ranges)
    average_silence_duration = (
        total_silent_duration_removed / number_of_cuts_made
        if number_of_cuts_made
        else 0
    )

    metrics = {
        "original_duration": original_duration,
        "final_duration": final_duration,
        "duration_reduction": duration_reduction,
        "total_silent_duration_removed": total_silent_duration_removed,
        "number_of_cuts_made": number_of_cuts_made,
        "average_silence_duration": average_silence_duration,
    }
    return metrics
