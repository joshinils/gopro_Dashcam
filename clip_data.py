import os
import subprocess
from typing import List, Optional

import GP_Highlight_Extractor


def get_date_taken(filename: str) -> str:
    p = subprocess.Popen(
        [
            "ffprobe",
            "-v", "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream_tags=creation_time",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    stdout, _ = p.communicate()
    return stdout.decode("ascii")[:10]


class ClipData:
    """
    data on individual file as is on disc
    """
    video_length: Optional[float]
    abs_filename: str
    base_filename: str
    offset: float
    hilights: Optional[List[float]]

    def __init__(self: 'ClipData', filename: str) -> None:
        self.video_length = None
        self.abs_filename = filename
        self.base_filename = os.path.basename(filename)
        self.hilights = None
        pass

    def get_hilights(self: 'ClipData') -> List[float]:
        if self.hilights is None:
            self.hilights = GP_Highlight_Extractor.get_hilights(self.abs_filename)

        return self.hilights

    def get_video_length(self: 'ClipData') -> float:
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

    def get_out_name(self: 'ClipData') -> str:
        return f"{get_date_taken(self.base_filename)}_{self.base_filename}"

    def __str__(self: 'ClipData') -> str:
        return self.abs_filename
