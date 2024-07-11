# ffmpeg_stream_sorter

ffmpeg_stream_sorter is a Python script designed to manipulate MKV video files, focusing on reordering audio and subtitle streams based on user-defined priorities, optionally adding subtitles, converting audio codecs, and organizing completed files.

You just downloaded Anime MKV files or other MKV files and want to quickly rename them, sort audio and/or subtitle streams and change default flags of these files? You maybe want to add an SRT file simultaniously? And on top of that convert specific audio stream codecs and define their bitrate? 

You need to have ffmpeg-python installed.

## Features

-Audio and Subtitle Prioritization: Prioritize and map/order audio and subtitle streams based on language and codec preferences.

-Subtitle Addition: Option to add external subrip files (SRT) to MKV videos.

-Audio Codec Conversion: Convert audio streams to specified codecs and bitrates.

-File Organization: Option to move completed MKV files to a new directory and rename them.

-Will delete FORCED subtitles.

-Will always default the first stream. (why? some TVs dont care about default tags, they will choose the first stream as default)

-Will delete all streams that are not in your priority lists









This repository contains example code and scripts provided without warranty or guarantee of any kind. Use of the code is at your own risk. The author assumes no responsibility for any damages or problems that may arise from the use of this code.

