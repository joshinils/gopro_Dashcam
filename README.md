# Dashcam-tools for GoPros

clips which overlap will be combined into one file.

where there are hilight markers there will be chapter markers in the extracted clip.

when a clip reaches into the previous or next video file (segmented video on the gopro) they will also be used to create a clip of the specified length

## cli-usage

``` preformatted
usage: main.py -i INPUT_PATHs) [INPUT_PATH(s ...] -o OUTPUT_FOLDER [-h]
               [--pre_t TIME_BEFORE] [--post_t TIME_AFTER]

GoPro Dashcam toolkit. Find and print HiLight tags for GoPro videos.

required named arguments:
    -i INPUT_PATH(s) [INPUT_PATH(s) ...]
    --input INPUT_PATH(s) [INPUT_PATH(s) ...]
        Folder(s) to search for videos (recursively)

    -o OUTPUT_FOLDER
    --output OUTPUT_FOLDER
        output video folder, where to put the extracted clips and intermediary
        files


optional arguments::
    -h
    --help
        show this help message and exit

    -pre_t TIME_BEFORE  (Default: 30)
    --pre_time TIME_BEFORE
        timespan to include before a HiLight mark, in seconds.

    -post_t TIME_AFTER  (Default: 10)
    --post_time TIME_AFTER
        timespan to include after a HiLight mark, in seconds.
```