from typing import List, Optional

from clip import Clip


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

