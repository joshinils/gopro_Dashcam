import os
import subprocess
from typing import Optional


class Clip:
    """
    a single clip in one file,
    there may be more than 1 clip per file
    """
    abs_filename: str
    base_filename: str
    start: float
    end: float
    video_length: Optional[float]
    date_taken: Optional[str]
    hilight_pos: int
    hilight_time: float

    def __init__(self: 'Clip', filename: str, start: float, end: float, hilight_pos: int, hilight_time: float) -> None:
        self.abs_filename = os.path.abspath(filename)
        self.base_filename = os.path.basename(filename)
        self.start = start
        self.end = end
        self.hilight_pos = hilight_pos
        self.hilight_time = hilight_time

        assert start < end  # yes no empty clips where start == end are allowed
        self.video_length = None
        self.date_taken = None

    def print_extraction(self: 'Clip', out_name: Optional[str] = None) -> str:
        if out_name is None:
            out_name = f"{self.base_filename}_extract.mkv"
        out_name = out_name.replace(os.sep * 2, os.sep)

        assert self.start >= 0.0, f"""start={self.start} is less than 0, setting to 0."""
        assert self.end >= 0.0, f"""end={self.end} is less than 0, setting to 0."""
        assert self.start <= self.get_video_length(), f"""start={self.start} is greater than clip length {self.get_video_length()}, setting to clip length."""
        assert self.end <= self.get_video_length(), f"""end={self.end} is greater than clip length {self.get_video_length()}, setting to clip length."""

        start_time = "" if self.start == 0.0 else f"-ss {self.start}"
        duration = self.end - self.start if self.end is not None else 0
        end_time = f"-t {duration}" if self.end is not None and self.end < self.get_video_length() else ""

        ffmetadata_file_name = f"{out_name}.ffmetadata"
        print(f"""ffmpeg -i "{self.abs_filename}" -f ffmetadata "{ffmetadata_file_name}\"""")
        print(f"""ffmpeg -i "{self.abs_filename}" {start_time} {end_time} -i "{ffmetadata_file_name}" -map_metadata 1 -codec copy "{out_name}" -y""".replace("  ", " ").replace("  ", " ").replace("  ", " "))
        print(f"""rm "{ffmetadata_file_name}\"""")
        return out_name

    def overlaps(self: 'Clip', other: 'Clip') -> bool:
        if self.abs_filename == other.abs_filename:
            # if the filename is the same perform a range-check:
            # https://stackoverflow.com/a/3269471/10314791
            return self.start <= other.end and other.start <= self.end
        else:
            # assume 'other' comes immediately after 'self' for later concatenation
            return self.start <= other.end + self.get_video_length() and other.start <= self.end + self.get_video_length()

    def clamp_start(self: 'Clip') -> None:
        if self.start < 0:
            self.start = 0

    def clamp_end(self: 'Clip') -> None:
        if self.end > self.get_video_length():
            self.end = self.get_video_length()

    def __repr__(self: 'Clip') -> str:
        length = self.video_length if self.video_length is not None else 0
        return f"CLIP=[{self.abs_filename=}, {self.start=: 19.14f}, {self.end=: 19.14f}, {self.hilight_pos=: 1}, {length=: 19.14f}, {self.date_taken=}]"

    def get_out_name(self: 'Clip') -> str:
        return f"{self.get_date_taken()}_{self.base_filename}"

    def get_video_length(self: 'Clip') -> float:
        if self.video_length is None:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    self.abs_filename
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            self.video_length = float(result.stdout)
        return self.video_length

    def get_date_taken(self: 'Clip') -> str:
        if self.date_taken is None:
            p = subprocess.Popen(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream_tags=creation_time",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    self.abs_filename
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            stdout, _ = p.communicate()
            self.date_taken = stdout.decode("ascii")[:10]
        return self.date_taken

    def __lt__(self: 'Clip', other: 'Clip') -> bool:
        if self is other:
            return False

        if self.base_filename == other.base_filename:
            return self.start < other.start
        else:
            return self.base_filename < other.base_filename
