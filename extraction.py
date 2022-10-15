import os
from copy import copy
from itertools import chain
from typing import List, Optional

from more_itertools import pairwise

from clip import Clip


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

    def combine_clips(self: "Extraction", file_name_first: str, file_name_second: str, file_name_combined: Optional[str] = None, clip_first: Optional[Clip] = None, clip_second: Optional[Clip] = None) -> str:
        if file_name_combined is None:
            file_name_combined = f"{os.path.basename(file_name_first)}_combine_{os.path.basename(file_name_second)}"
        file_name_combined = f"{self.output_path}{os.sep}{os.path.basename(file_name_combined)}".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep)
        list_name = f"""{self.output_path}{os.sep}{os.path.basename(file_name_combined)}.ffmpeg_combine_list""".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep)

        # setup list of files to be combined for ffmpeg
        print(f"""echo "" > "{list_name}\"""")
        print(f"""echo "file '{file_name_first}'" >> "{list_name}\"""")
        print(f"""echo "file '{file_name_second}'" >> "{list_name}\"""")

        # export metadata
        ffmetadata_file_name = f"{file_name_first}.ffmetadata"
        print(f"""ffmpeg -i "{file_name_first}" -f ffmetadata "{ffmetadata_file_name}\"""")

        # # append second metadata
        # for hilight_time in second_clip.hilights:
        #     start_time = first_clip.length + hilight_time
        #     print(f""" echo "[CHAPTER]" >> "{ffmetadata_file_name}\"""")
        #     print(f""" echo "TIMEBASE=1/{denominator}" >> "{ffmetadata_file_name}\"""")
        #     print(f""" echo "START={start_time}" >> "{ffmetadata_file_name}\"""")

        # combine
        print(f"""ffmpeg -f concat -safe 0 -i "{list_name}" -i "{ffmetadata_file_name}" -map_metadata 1 -c copy "{file_name_combined}" -y""")

        # cleanup
        print(f"""rm -f "{file_name_first}" "{file_name_second}" "{ffmetadata_file_name}" "{list_name}\"""")
        return file_name_combined

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

    @staticmethod
    def add_metadata(in_name: str, out_name: str, hilights: List[float]) -> str:
        ffmetadata_file_name = f"{in_name}.ffmetadata"
        print(f"""ffmpeg -i "{in_name}" -f ffmetadata "{ffmetadata_file_name}\"""")
        print(f"""ffmpeg -i "{in_name}" -i "{ffmetadata_file_name}" -map_metadata 1 -codec copy "{out_name}\"""")
        # print(f"""rm "{in_name}\"""")
        # print(f"""rm "{ffmetadata_file_name}\"""")
        return out_name

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
            clip_0_name = clips[0].print_extraction(f"{self.output_path}{os.sep}{clips[0].get_out_name()}_extract_1_of2_s={clips[0].start}.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))
            clip_1_name = clips[1].print_extraction(f"{self.output_path}{os.sep}{clips[1].get_out_name()}_extract_2_of2_s={clips[1].start}.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))

            return self.combine_clips(clip_0_name, clip_1_name, out_name)

        # combine 3 or more clips
        clip_names: List[str] = []
        hilights = []
        for num, clip in enumerate(clips):
            clip_name = clip.print_extraction(f"{self.output_path}{os.sep}{clip.get_out_name()}_extract_{num}_of_M_s={clip.start}.mkv".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep))
            clip_names.extend([clip_name])
            hilights.append(clip.hilight_time)

        current_clip_name = clip_names[0]
        for clip_name in clip_names[1:-1]:
            current_clip_name = self.combine_clips(current_clip_name, clip_name)

        return self.combine_clips(current_clip_name, clip_names[-1], out_name)

    def __repr__(self: 'Extraction') -> str:
        ret = "EXTRACTION=[clips=\n"
        for clip in self.clips:
            ret += clip.__repr__() + "\n"
        ret += "][ cleaned=\n"
        for clip in self.get_clean_clip_lengths():
            ret += clip.__repr__() + "\n"
        ret += "] </EXTRACTION>"
        return ret
