import os
from copy import copy
from itertools import chain
from typing import List, Optional

from more_itertools import pairwise

from clip import Clip


def combine_clips(file_name_first: str, file_name_second: str, file_name_combined: Optional[str] = None) -> str:
    # print(f"{file_name_first=}")
    # print(f"{file_name_second=}")
    # print(f"{file_name_combined=}")

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


class Extraction:
    """
    A list of 'Clip's
    a single extraction from 1 or more clips.
    If more than one clip, they will be combined
    """
    clips: List[Clip]
    output_path: str

    def __init__(self: 'Extraction', extraction_number: int, output_path: str) -> None:
        self.extraction_number = extraction_number
        self.clips = []
        self.output_path = output_path

    def add_clip(self: 'Extraction', clip: Clip) -> None:
        self.clips.append(clip)

    def get_clean_clip_lengths(self: 'Extraction') -> List[Clip]:
        clips_copy = sorted(self.clips)

        # make sure the clips overlap!
        for clip, next_clip in pairwise(clips_copy):
            assert clip.overlaps(next_clip)

        returnable: List[Clip] = []

        clamp_next_start = True  # clamp first clip, always
        next_start_time: Optional[float] = None
        for clip, next_clip in pairwise(chain(clips_copy, [None])):
            this_clip = copy(clip)
            if clamp_next_start:
                clamp_next_start = False
                this_clip.clamp_start()
            if next_start_time is not None:
                this_clip.start = next_start_time
                next_start_time = None

            if next_clip is not None and this_clip.base_filename == next_clip.base_filename:
                # same file, remove one clip, change ending accordingly
                next_start_time = this_clip.start
            else:
                # differing files, clamp end/start and append
                this_clip.clamp_end()
                clamp_next_start = True
                returnable.append(this_clip)

        return returnable

    def print_extraction(self: 'Extraction', out_name: Optional[str] = None) -> Optional[str]:
        clips = self.get_clean_clip_lengths()

        if len(clips) <= 0:
            return None

        if out_name is None:
            for clip in self.clips:
                if clip.hilight_pos == 0:
                    out_name = f"{self.output_path}{os.sep}{clip.get_out_name()}_clip_{self.extraction_number:03}.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep)
                    break

        assert out_name is not None

        if len(clips) == 1:
            return clips[0].print_extraction(out_name)

        if len(clips) == 2:
            clip_0_name = clips[0].print_extraction(f"{self.output_path}{os.sep}{clips[0].get_out_name()}_extract_1_of2.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))
            clip_1_name = clips[1].print_extraction(f"{self.output_path}{os.sep}{clips[1].get_out_name()}_extract_2_of2.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))

            return combine_clips(clip_0_name, clip_1_name, out_name)

        # combine 3 or more clips
        clip_names: List[str] = []
        for num, clip in enumerate(clips):
            clip_name = clip.print_extraction(f"{self.output_path}{os.sep}{clip.get_out_name()}_extract_{num}_of_M.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))
            clip_names.extend([clip_name])

        current_clip_name = clip_names[0]
        for clip_name in clip_names[1:-1]:
            current_clip_name = combine_clips(current_clip_name, clip_name)
        return combine_clips(current_clip_name, clip_names[-1], out_name)

    def __repr__(self: 'Extraction') -> str:
        ret = "EXTRACTION=[clips=\n"
        for clip in self.clips:
            ret += clip.__repr__() + "\n"
        ret += "][ cleaned=\n"
        for clip in self.get_clean_clip_lengths():
            ret += clip.__repr__() + "\n"
        ret += "] </EXTRACTION>"
        return ret
