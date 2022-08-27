#!/usr/bin/env python3

import argparse
import itertools
import os
import subprocess
import sys
from itertools import chain
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Set

from more_itertools import pairwise
from pymediainfo import MediaInfo

import GP_Highlight_Extractor


def triplewise(iterable: Iterable) -> Generator:
    "Return overlapping triplets from an iterable"
    # triplewise('ABCDEFG') -> ABC BCD CDE DEF EFG
    for (a, _), (b, c) in pairwise(pairwise(chain([None], iterable, [None]))):
        yield a, b, c


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""
        GoPro Dashcam toolkit.
        Find and print HiLight tags for GoPro videos.
        """
    )

    requiredNamed = parser.add_argument_group('required named arguments')

    requiredNamed.add_argument("-i", "--input", metavar="INPUT_PATH(s)", required=True, help="Folder to search for videos", type=str, nargs='+', action="append")
    requiredNamed.add_argument("-o", "--output", metavar="OUTPUT_FOLDER", required=True, help="output video folder, where to put the extracted clips", type=str)

    parser.add_argument("--pre_t", metavar="TIME_BEFORE", help="time before a HiLight mark, in seconds. default=30sec", type=float, default=30)
    parser.add_argument("--post_t", metavar="TIME_AFTER", help="time after a HiLight mark, in seconds. default=10sec", type=float, default=10)
    return parser.parse_args()


def is_existing_file(filename: str) -> bool:
    return (
        os.path.exists(filename.rstrip(os.sep)) is True  # is a valid path
        and
        os.path.exists(filename.rstrip(os.sep) + os.sep) is False  # is not a folder, i.e. not valid with trailing / slash
    )


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


class Extraction:
    """
    a single extraction from 1 or more clips.
    If more than one clip, they will be combined
    """
    clips: List[Clip]

    def __init__(self: 'Extraction') -> None:
        self.clips = []

    def add_clip(self: 'Extraction', clip: Clip) -> None:
        self.clips.append(clip)

    def print_extraction(self: 'Extraction', out_name: str) -> Optional[str]:
        if len(self.clips) <= 0:
            return None

        if len(self.clips) == 1:
            return self.clips[0].print_extraction(out_name)

        if len(self.clips) == 2:
            clip_0_name = self.clips[0].print_extraction()
            clip_1_name = self.clips[1].print_extraction()

            return combine_clips(clip_0_name, clip_1_name, out_name)

        # combine 3 or more clips
        clip_names: List[str] = []
        for clip in self.clips:
            clip_name = clip.print_extraction()
            clip_names.extend(clip_name)

        current_clip_name = clip_names[0]
        for clip_name in clip_names[1:-1]:
            current_clip_name = combine_clips(current_clip_name, clip_name)
        return combine_clips(current_clip_name, clip_names[-1], out_name)


def is_video_file(filename: str) -> bool:
    fileInfo = MediaInfo.parse(filename)
    for track in fileInfo.tracks:
        if track.track_type == "Video":
            return True
    return False


def split_file_list_single_recording(lst: List[str]) -> List[List[ClipData]]:
    folder_dict: Dict[str, Set[str]] = dict()
    for abs_name in lst:
        filename = os.path.basename(abs_name)
        if abs_name.endswith(filename):
            if abs_name[:-len(filename)] not in folder_dict:
                folder_dict[abs_name[:-len(filename)]] = set()
            folder_dict[abs_name[:-len(filename)]].add(abs_name)

    folder_content_list = []
    for _, folder_set in folder_dict.items():
        folder_content_list.append(sorted(list(folder_set)))

    result_lists = []
    for folder in folder_content_list:
        groups: Dict[str, Set[str]] = dict()
        for file in folder:
            filename = os.path.basename(file)
            # https://community.gopro.com/s/article/GoPro-Camera-File-Naming-Convention?language=en_US
            group_name = filename[0:4]
            if group_name not in groups:
                groups[group_name] = set()
            if is_video_file(file):
                groups[group_name].add(file)
            else:
                print(f"""Input file "{file}" is not a video file! ignoring it.""", file=sys.stderr)

        for group_name, group_set in groups.items():
            result_lists.append([ClipData(filename) for filename in sorted(list(group_set))])

    return result_lists


def get_files_in_folder(folder: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


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


def combine_clips(file_name_first: str, file_name_second: str, file_name_combined: Optional[str] = None) -> str:
    if file_name_combined is None:
        file_name_combined = f"{file_name_first}.combine.{file_name_second}"
    list_name = f"{file_name_combined}.ffmpeg_combine_list"

    # setup list of files to be combined for ffmpeg
    print(f"""echo "" > {list_name}""")
    print(f"""echo "file '{file_name_first}'" >> {list_name}""")
    print(f"""echo "file '{file_name_second}'" >> {list_name}""")

    # combine
    print(f"""ffmpeg -f concat -safe 0 -i {list_name} -c copy {file_name_combined} -y""")

    # cleanup
    print(f"rm -f {file_name_first} {file_name_second}")
    print(f"""rm {list_name}""")
    return file_name_combined


def main() -> None:
    args = parse_arguments()
    # print(args)

    input_paths: List[str] = list(itertools.chain.from_iterable(args.input))
    output_path: str = args.output

    # filter nonexistent input_paths
    for path in input_paths:
        if not os.path.exists(path):
            print(f"""Input path "{path}" does not exist! ignoring it.""", file=sys.stderr)
    input_paths = [path for path in input_paths if os.path.exists(path)]

    input_path: str
    for input_path in input_paths:
        input_path = os.path.abspath(input_path)
        # print(input_path, os.path.abspath(input_path))
        if not os.path.exists(input_path):
            raise ValueError(f"""Input Path "{input_path}" does not exist!""")

    input_filenames: list = []
    for input_path in input_paths:
        input_path = os.path.abspath(input_path)
        if is_existing_file(input_path):
            input_filenames.append(input_path)
        else:
            input_filenames.extend(get_files_in_folder(input_path))

    input_filenames = [filename if os.path.exists(filename) else print(f"""Input filename "{filename}" does not exist!""", file=sys.stderr) for filename in input_filenames if os.path.exists(filename)]

    input_recordings_ClipData: List[List[ClipData]] = split_file_list_single_recording(input_filenames)

    time_before: float = args.pre_t
    time_after: float = args.post_t

    Path(output_path).mkdir(parents=True, exist_ok=True)

    for recording in input_recordings_ClipData:
        total_clips: int = 0
        for clip in recording:
            total_clips += len(clip.get_hilights())
        total_clips = max(len(str(total_clips)), 2)

        prev_ClipData: Optional[ClipData]
        this_ClipData: ClipData
        next_ClipData: Optional[ClipData]
        clip_index: int = 0
        for prev_ClipData, this_ClipData, next_ClipData in triplewise(recording):
            try:
                if len(this_ClipData.get_hilights()) == 0:
                    continue

                # print(this_ClipData, this_ClipData.get_hilights())
                for hilight_time in this_ClipData.get_hilights():
                    if time_before + time_after > this_ClipData.get_video_length() / 2:
                        # avoid having to use both the previous _and_ the next clip, so only concatenation of at most two clips is necessary
                        print(f"time_before={time_before}, time_after={time_after}, clip={this_ClipData.get_video_length()}", file=sys.stderr)
                        print(f"{this_ClipData.abs_filename}", file=sys.stderr)
                        raise ValueError("the time before and after are too long together, choose shorter clips to extract")

                    use_prev_clip = prev_ClipData is not None and hilight_time - time_before < 0
                    use_next_clip = next_ClipData is not None and hilight_time + time_after > this_ClipData.get_video_length()

                    prev_name = f"{output_path}{os.sep}{prev_ClipData.get_out_name()}_clip_{clip_index:0>{total_clips}d}" if prev_ClipData is not None else ""
                    this_name = f"{output_path}{os.sep}{this_ClipData.get_out_name()}_clip_{clip_index:0>{total_clips}d}"
                    next_name = f"{output_path}{os.sep}{next_ClipData.get_out_name()}_clip_{clip_index:0>{total_clips}d}" if next_ClipData is not None else ""

                    if use_prev_clip and prev_ClipData is not None:
                        next_time_end = prev_ClipData.get_video_length() + hilight_time - time_before
                        extract_clip(prev_ClipData, f"{prev_name}_prev.mkv", start=next_time_end)
                        extract_clip(this_ClipData, f"{this_name}_this.mkv", end=hilight_time + time_after)

                        combine_clips(f"{prev_name}_prev.mkv", f"{this_name}_this.mkv", f"{this_name}.mkv")

                    if use_prev_clip is False and use_next_clip is False:
                        extract_clip(this_ClipData, f"{this_name}.mkv", start=hilight_time - time_before, end=hilight_time + time_after)

                    if use_next_clip and next_ClipData is not None:
                        next_time_end = hilight_time + time_after - this_ClipData.get_video_length()
                        extract_clip(this_ClipData, f"{this_name}_this.mkv", start=hilight_time - time_before)
                        extract_clip(next_ClipData, f"{next_name}_next.mkv", end=next_time_end)

                        combine_clips(f"{this_name}_this.mkv", f"{next_name}_next.mkv", f"{this_name}.mkv")

                    clip_index += 1
            except Exception as e:
                print(e, file=sys.stderr)
        print()


if __name__ == "__main__":
    main()
