#!/usr/bin/env python3

import argparse
import os
from pathlib import Path

import GP_Highlight_Extractor


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""
        GoPro Dashcam toolkit.
        Find and print HiLight tags for GoPro videos.
        """
    )

    requiredNamed = parser.add_argument_group('required named arguments')

    requiredNamed.add_argument("-i", "--input", metavar="INPUT_PATH(s)", required=True, help="Folder to search for videos", type=str, nargs='+')
    requiredNamed.add_argument("-o", "--output", metavar="OUTPUT_NAME", required=True, help="output video folder", type=str)

    # parser.add_argument("--foo", help="help", type=int, default=0)
    return parser.parse_args()


def is_existing_file(filename: str) -> bool:
    return (
        os.path.exists(filename.rstrip(os.sep)) is True  # is a valid path
        and
        os.path.exists(filename.rstrip(os.sep) + os.sep) is False  # is not a folder, i.e. not valid with trailing / slash
    )


def main() -> None:
    args = parse_arguments()
    # print(args)

    input_paths: str = args.input
    output_path: str = args.output

    input_path: str
    for input_path in input_paths:
        print(input_path)
        if not os.path.exists(input_path):
            raise ValueError(f"""Input Path "{input_path}" does not exist!""")

    input_filenames: list = []
    for input_path in input_paths:
        if is_existing_file(input_path):
            input_filenames.append(input_path)
        else:
            input_filenames.extend(next(os.walk(input_path), (None, None, []))[2])  # [] if no file

    for filename in input_filenames:
        if not os.path.exists(filename):
            raise ValueError(f"""Input filename "{filename}" does not exist!""")

    Path(output_path).mkdir(parents=True, exist_ok=True)

    for input_filename in input_filenames:
        try:
            highlights = GP_Highlight_Extractor.get_highlights([input_filename])
            print(input_filename, highlights)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    main()
