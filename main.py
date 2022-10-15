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

from clip import Clip
from extraction import Extraction
from video_file_data import VideoFileData


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


def is_video_file(filename: str) -> bool:
    fileInfo = MediaInfo.parse(filename)
    for track in fileInfo.tracks:
        if track.track_type == "Video":
            return True
    return False


def split_file_list_single_recording(lst: List[str]) -> List[List[VideoFileData]]:
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
            result_lists.append([VideoFileData(filename) for filename in sorted(list(group_set))])

    return result_lists


def get_files_in_folder(folder: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def extract_clip(video_file_data: VideoFileData, out_name: Optional[str], start: float = 0.0, end: Optional[float] = None) -> str:
    if out_name is None:
        out_name = f"{video_file_data.base_filename}_extract.mkv"
    out_name = out_name.replace(os.sep * 2, os.sep)

    if start and start < 0.0:
        start = 0
        print(f"""start={start} is less than 0, setting to 0.""", file=sys.stderr)

    if end and end < 0.0:
        end = 0
        print(f"""end={end} is less than 0, setting to 0.""", file=sys.stderr)

    if start and start > video_file_data.get_video_length():
        start = video_file_data.get_video_length()
        print(f"""start={start} is greater than clip length {video_file_data.get_video_length()}, setting to clip length.""", file=sys.stderr)

    if end and end > video_file_data.get_video_length():
        end = video_file_data.get_video_length()
        print(f"""end={end} is greater than clip length {video_file_data.get_video_length()}, setting to clip length.""", file=sys.stderr)

    start_time = "" if start == 0.0 else f"-ss {start}"
    duration = end - start if end is not None else 0
    end_time = f"-t {duration}" if end is not None and end < video_file_data.get_video_length() else ""
    print(f"""ffmpeg -i "{video_file_data.abs_filename}" {start_time} {end_time} -codec copy "{out_name}" -y""".replace("  ", " "))
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

    input_recordings_VideoFileData: List[List[VideoFileData]] = split_file_list_single_recording(input_filenames)

    time_before: float = args.pre_t
    time_after: float = args.post_t

    Path(output_path).mkdir(parents=True, exist_ok=True)

    for recording in input_recordings_VideoFileData:
        total_clips: int = 0
        for video_file in recording:
            total_clips += len(video_file.get_hilights())
        total_clips = max(len(str(total_clips)), 2)

        clips: List[Clip] = []

        previous_video_file_data: Optional[VideoFileData]
        video_file_data: VideoFileData
        next_video_file_data: Optional[VideoFileData]
        for previous_video_file_data, video_file_data, next_video_file_data in triplewise(recording):
            try:
                if len(video_file_data.get_hilights()) == 0:
                    continue

                for hilight_time in video_file_data.get_hilights():
                    hilight_start = hilight_time - time_before
                    hilight_end = hilight_time + time_after

                    # use previous clip
                    if previous_video_file_data is not None and hilight_start < 0:
                        # assumes overhang into previous clip is shorter than the previous clip is long
                        # otherwise only all of the previous clip will be used
                        assert previous_video_file_data.get_video_length() + hilight_start >= 0

                        clips.append(
                            Clip(
                                previous_video_file_data.abs_filename,
                                start=previous_video_file_data.get_video_length() + hilight_start,
                                end=previous_video_file_data.get_video_length() + hilight_end,
                                hilight_pos=+1,
                                hilight_time=hilight_time,
                            )
                        )

                    # use the clip where the hilight is
                    clips.append(
                        Clip(
                            video_file_data.abs_filename,
                            start=hilight_start,
                            end=hilight_end,
                            hilight_pos=0,
                            hilight_time=hilight_time,
                        )
                    )

                    # use next clip
                    if next_video_file_data is not None and hilight_end > video_file_data.get_video_length():
                        # clip length depends on this clip, not the next
                        # thus subtract this clip length from clip end and start to get the
                        # start and end times in the next clip, no matter how long it is

                        # assumes overhang into next clip is shorter than the next clip is long
                        # otherwise only all of the next clip will be used
                        assert -video_file_data.get_video_length() + hilight_end <= next_video_file_data.get_video_length()

                        clips.append(
                            Clip(
                                next_video_file_data.abs_filename,
                                start=-video_file_data.get_video_length() + hilight_start,
                                end=-video_file_data.get_video_length() + hilight_end,
                                hilight_pos=-1,
                                hilight_time=hilight_time,
                            )
                        )

            except Exception as e:
                print(e, file=sys.stderr)

        clips.sort()

        clip: Clip
        next_clip: Optional[Clip]
        extractions: List[Extraction] = []  # per recording
        extraction_number = 0
        current_extraction = Extraction(extraction_number=extraction_number, output_path=output_path)

        for clip, next_clip in pairwise(chain(clips, [None])):
            current_extraction.add_clip(clip)
            if (
                next_clip is None  # no next clip to add, stop
                or not clip.overlaps(next_clip)  # clips not overlapping, start next extraction
            ):
                extractions.append(current_extraction)  # finish compiling clips in extraction
                current_extraction = Extraction(extraction_number=(extraction_number := extraction_number + 1), output_path=output_path)  # reset extraction

        for extraction in extractions:
            extraction.print_extraction()


if __name__ == "__main__":
    main()
