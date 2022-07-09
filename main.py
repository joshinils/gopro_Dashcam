#!/usr/bin/env python3

import argparse
import itertools
import os
import subprocess
import sys
import typing
from pathlib import Path

from pymediainfo import MediaInfo

import GP_Highlight_Extractor


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


class ClipData:
    video_length: typing.Optional[float]
    filename: str

    def __init__(self: 'ClipData', filename: str) -> None:
        self.video_length = None
        self.filename = filename
        pass

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
                    self.filename
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            self.video_length = float(result.stdout)
        return self.video_length

    def __str__(self: 'ClipData') -> str:
        return self.filename


def is_video_file(filename: str) -> bool:
    fileInfo = MediaInfo.parse(filename)
    for track in fileInfo.tracks:
        if track.track_type == "Video":
            return True
    return False


def split_file_list_single_recording(lst: typing.List[str]) -> typing.List[typing.List[ClipData]]:
    folder_dict: typing.Dict[str, typing.Set[str]] = dict()
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
        groups: typing.Dict[str, typing.Set[str]] = dict()
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


def get_files_in_folder(folder: str) -> typing.Iterable[str]:
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def extract_clip() -> None:
    # ffmpeg -i GHAC6566.MP4 -ss 160.38 -t 10 -codec copy /media/data_nvme0n1p1/gopro_Dashcam/clip1.mp4
    pass


def main() -> None:
    args = parse_arguments()
    print(args)

    input_paths: typing.List[str] = list(itertools.chain.from_iterable(args.input))
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

    input_recordings_ClipData: typing.List[typing.List[ClipData]] = split_file_list_single_recording(input_filenames)

    time_before: float = args.pre_t
    time_after: float = args.post_t

    for recording in input_recordings_ClipData:
        prev_ClipData: typing.Optional[ClipData]
        this_ClipData: ClipData
        next_ClipData: typing.Optional[ClipData]

        prev_list: typing.List[typing.Optional[ClipData]] = [None]
        prev_list.extend(recording[:-1])

        next_list: typing.List[typing.Optional[ClipData]] = [None]
        next_list[0:0] = recording[1:]

        for prev_ClipData, this_ClipData, next_ClipData in zip(prev_list, recording, next_list):
            try:
                highlights = GP_Highlight_Extractor.get_highlights([this_ClipData.filename])
                print(this_ClipData, highlights)
                for highlight in highlights:
                    use_prev_clip = prev_ClipData is not None and highlight - time_before < 0
                    use_next_clip = next_ClipData is not None and highlight + time_after > this_ClipData.get_video_length()

                    print(use_prev_clip, use_next_clip)

            except Exception as e:
                print(e)
        print()

    Path(output_path).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
