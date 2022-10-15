import os
from copy import copy
from fractions import Fraction
from itertools import chain
from typing import List, Optional

from more_itertools import pairwise

from clip import Clip
from run_bash import run_bash


class Extraction:
    """
    A list of 'Clip's
    a single extraction from 1 or more clips.
    If more than one clip, they will be combined
    """
    clips: List[Clip]
    output_path: str

    combine_file_path: str

    def __init__(self: 'Extraction', extraction_number: int, output_path: str) -> None:
        self.extraction_number = extraction_number
        self.clips = []
        self.output_path = (output_path + os.sep).replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep)
        self.combine_file_path = f"""{self.output_path}{os.sep}combine_{extraction_number}.ffmpeg_combine_list""".replace(os.sep * 2, os.sep).replace(os.sep * 2, os.sep)

    def add_clip(self: 'Extraction', clip: Clip) -> None:
        self.clips.append(clip)

    def extract_and_combine_all_clips(self: "Extraction", *, out_file_name: str) -> str:
        extract_filenames = []
        for index, clip in enumerate(self.clips):
            extract_filenames.append(clip.create_clip_extraction(f"""{self.output_path}extraction_{self.extraction_number}_{clip.base_filename}_clip_{index+1}_of_{len(self.clips)}.mkv"""))

        with open(self.combine_file_path, "w") as file:
            for extract_filename in extract_filenames:
                file.write(f"file '{extract_filename}'\n")

        out_file_name = f"{self.output_path}{os.path.basename(out_file_name)}"

        # export metadata
        ffmetadata_file_name = f"{self.output_path}combine_{self.extraction_number}.ffmetadata"
        run_bash(f"""ffmpeg -hide_banner -loglevel error -stats -i "{self.clips[0].abs_filename}" -f ffmetadata "{ffmetadata_file_name} -y\"""")

        # remove other chapter markers
        with open(ffmetadata_file_name, "r") as ffmetadata_file:
            metadata = ffmetadata_file.read()
        with open(ffmetadata_file_name, "w") as ffmetadata_file:
            ffmetadata_file.write(metadata.split("[CHAPTER]")[0])

        # add metadata for other clips
        if len(self.clips) > 1:
            prev_time = 0.0
            for clip in self.clips:
                frac = Fraction(prev_time + clip.hilight_time - clip.start)
                limited = frac.limit_denominator(10000)
                with open(ffmetadata_file_name, "a") as ffmetadata_file:
                    ffmetadata_file.write("[CHAPTER]\n")
                    ffmetadata_file.write(f"TIMEBASE=1/{limited.denominator}\n")
                    ffmetadata_file.write(f"START={limited.numerator}\n")
                    ffmetadata_file.write(f"END={limited.numerator}\n")
                prev_time += clip.get_clip_length()

        # combine
        run_bash(f"""ffmpeg -hide_banner -loglevel error -stats -f concat -safe 0 -i "{self.combine_file_path}" -i "{ffmetadata_file_name}" -map_metadata 1 -c copy "{out_file_name}" -y""")

        # cleanup
        run_bash(f"""rm -f "{self.combine_file_path}"\"""")
        run_bash(f"""rm -f "{ffmetadata_file_name}"\"""")
        for extract_filename in extract_filenames:
            run_bash(f"""rm -f "{extract_filename}"\"""")

        return out_file_name

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
        run_bash(f"""ffmpeg -hide_banner -loglevel error -stats -i "{in_name}" -f ffmetadata "{ffmetadata_file_name}\"""")
        run_bash(f"""ffmpeg -hide_banner -loglevel error -stats -i "{in_name}" -i "{ffmetadata_file_name}" -map_metadata 1 -codec copy "{out_name}\"""")
        # run_bash(f"""rm "{in_name}\"""")
        # run_bash(f"""rm "{ffmetadata_file_name}\"""")
        return out_name

    def create_extraction(self: 'Extraction', out_name: Optional[str] = None) -> Optional[str]:
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
            return clips[0].create_clip_extraction(out_name)

        return self.extract_and_combine_all_clips(out_file_name=out_name)

    def __repr__(self: 'Extraction') -> str:
        ret = "EXTRACTION=[clips=\n"
        for clip in self.clips:
            ret += clip.__repr__() + "\n"
        ret += "][ cleaned=\n"
        for clip in self.get_clean_clip_lengths():
            ret += clip.__repr__() + "\n"
        ret += "] </EXTRACTION>"
        return ret
