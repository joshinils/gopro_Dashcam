"""
GoPro Highlight Parser:  https://github.com/icegoogles/GoPro-Highlight-Parser

The code for extracting the mp4 boxes/atoms is from 'Human Analog' (https://www.kaggle.com/humananalog):
https://www.kaggle.com/humananalog/examine-mp4-files-with-python-only

"""

# from https://github.com/icegoogles/GoPro-Highlight-Parser

import struct
import sys
import typing
from math import floor


def find_boxes(file_stream: typing.BinaryIO, start_offset: int = 0, end_offset: int = sys.maxsize) -> typing.Dict[bytes, typing.Tuple[int, int]]:
    """Returns a dictionary of all the data boxes and their absolute starting
    and ending offsets inside the video file.

    Specify a start_offset and end_offset to read sub-boxes.
    """
    s = struct.Struct("> I 4s")
    boxes = {}
    offset = start_offset
    file_stream.seek(offset, 0)
    while offset < end_offset:
        # read box header
        data = file_stream.read(8)
        if data == b"":
            # EOF
            break
        length, text = s.unpack(data)
        file_stream.seek(length - 8, 1)          # skip to next box
        boxes[text] = (offset, offset + length)
        offset += length
    return boxes


def parse_highlights(file_stream: typing.BinaryIO, start_offset: int = 0, end_offset: int = sys.maxsize) -> typing.List[float]:
    inHighlights = False
    inHLMT = False

    listOfHighlights = []

    offset = start_offset
    file_stream.seek(offset, 0)

    while offset < end_offset:
        # read box header
        data = file_stream.read(4)
        if data == b"":  # EOF
            break

        if data == b'High' and inHighlights is False:
            data = file_stream.read(4)
            if data == b'ligh':
                inHighlights = True  # set flag, that highlights were reached

        if data == b'HLMT' and inHighlights is True and inHLMT is False:
            inHLMT = True  # set flag that HLMT was reached

        if data == b'MANL' and inHighlights is True and inHLMT is True:

            currPos = file_stream.tell()  # remember current pointer/position
            file_stream.seek(currPos - 20)  # go back to highlight timestamp

            data = file_stream.read(4)  # readout highlight
            timestamp = int.from_bytes(data, "big")

            if timestamp != 0:
                listOfHighlights.append(timestamp / 1000)

            file_stream.seek(currPos)  # go forward again (to the saved position)

    return listOfHighlights


def examine_file(filename: str) -> typing.List[float]:
    file_stream: typing.BinaryIO
    with open(filename, "rb") as file_stream:
        boxes = find_boxes(file_stream)

        # Sanity check that this really is a movie file.
        if b"ftyp" not in boxes or boxes[b"ftyp"][0] != 0:
            raise ValueError(f"""ERROR, file "{filename}" is not an mp4-video-file!""")

        moov_boxes = find_boxes(file_stream, boxes[b"moov"][0] + 8, boxes[b"moov"][1])
        udta_boxes = find_boxes(file_stream, moov_boxes[b"udta"][0] + 8, moov_boxes[b"udta"][1])

        # get GPMF Box
        return parse_highlights(file_stream, udta_boxes[b'GPMF'][0] + 8, udta_boxes[b'GPMF'][1])


def sec2dtime(secs: float) -> str:
    """converts seconds to datetimeformat"""
    milsec = (secs - floor(secs)) * 1000
    secs = secs % (24 * 3600)
    hour = secs // 3600
    secs %= 3600
    min = secs // 60
    secs %= 60

    return "%d:%02d:%02d.%03d" % (hour, min, secs, milsec)


def get_highlights(fNames: typing.List[str]) -> typing.List[float]:
    highlights = []
    for fName in fNames:
        highlights.extend(examine_file(fName))
    highlights.sort()

    return highlights
