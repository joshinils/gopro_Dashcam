import os
import sys
from typing import Optional

from clip_data import ClipData


def extract_clip(clip_data: ClipData, out_name: Optional[str], start: float = 0.0, end: Optional[float] = None) -> str:
    if out_name is None:
        out_name = f"{clip_data.base_filename}_extract.mkv"
    out_name = out_name.replace(os.sep * 2, os.sep)

    if start and start < 0.0:
        start = 0
        print(f"""start={start} is less than 0, setting to 0.""", file=sys.stderr)

    if end and end < 0.0:
        end = 0
        print(f"""end={end} is less than 0, setting to 0.""", file=sys.stderr)

    if start and start > clip_data.get_video_length():
        start = clip_data.get_video_length()
        print(f"""start={start} is greater than clip length {clip_data.get_video_length()}, setting to clip length.""", file=sys.stderr)

    if end and end > clip_data.get_video_length():
        end = clip_data.get_video_length()
        print(f"""end={end} is greater than clip length {clip_data.get_video_length()}, setting to clip length.""", file=sys.stderr)

    start_time = "" if start == 0.0 else f"-ss {start}"
    duration = end - start if end is not None else 0
    end_time = f"-t {duration}" if end is not None and end < clip_data.get_video_length() else ""
    print(f"""ffmpeg -i "{clip_data.abs_filename}" {start_time} {end_time} -codec copy "{out_name}" -y""".replace("  ", " "))
    return out_name


class Clip:
    """
    a single clip in one file,
    there may be more than 1 clip per file
    """
    filename: str
    start: float
    end: float

    def __init__(self: 'Clip', filename: str, start: float, end: float) -> None:
        self.filename = filename
        self.start = start
        self.end = end

    def print_extraction(self: 'Clip', out_name: Optional[str] = None) -> str:
        return extract_clip(ClipData(self.filename), out_name=out_name, start=self.start, end=self.end)
