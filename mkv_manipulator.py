from pathlib import Path
import ffmpeg
import pandas as pd
import os
import shutil


class Manipulator:
    def __init__(self, file_path, a_language_priority: list, s_language_priority: list,
                 a_codec_priority, s_codec_priority, add_srt: dict, convert_audio, move_completed_files: bool,
                 nan_language: str):
        self.path = Path(file_path)
        self.files = []
        self._initialize_files()

        self.a_language_priority = a_language_priority
        self.s_language_priority = s_language_priority

        self.a_codec_priority = a_codec_priority
        self.s_codec_priority = s_codec_priority

        self.add_srt = add_srt

        self.convert_audio = convert_audio

        self.move_completed_files = move_completed_files

        self.nan_language = nan_language

        self.mapper_a = []
        self.mapper_s = []

        self.metadata = {}
        self.disposition = {}

    def _initialize_files(self):

        if not self.path.exists():
            raise ValueError(f"Path {self.path} does not exist.")

        if self.path.is_dir():
            self.files = list(self.path.glob('*.mkv'))
            print(f"Folder found. Number of MKV files: {len(self.files)}")
            if not self.files:
                raise ValueError(f"No MKV files found in the directory {self.path}.")
        elif self.path.is_file():
            if self.path.suffix.lower() == '.mkv':
                self.files = [self.path]
                print(f"File found. Name: {self.files}")
            else:
                raise ValueError(f"File {self.path} is not an MKV file.")
        else:
            raise ValueError(f"{self.path} is neither a file nor a directory.")

    @staticmethod
    def create_output_path(input_path):
        directory, filename = os.path.split(input_path)
        name, extension = os.path.splitext(filename)

        new_path = input_path
        counter = 1

        while os.path.exists(new_path):
            new_filename = f"{name}_{counter}{extension}"
            new_path = os.path.join(directory, new_filename)
            counter += 1

        print(f"Output_path: {new_path}")

        return new_path

    @staticmethod
    def create_srt_file_name(input_path):
        directory, filename = os.path.split(input_path)
        name, extension = os.path.splitext(filename)

        srt_path = f"{name}.srt"
        new_path = os.path.join(directory, srt_path)
        print(f"SRT_path: {new_path}")

        return new_path

    @staticmethod
    def move_files_and_rename(file):

        dir_name, file_name_with_ext = os.path.split(file)
        file_name, _ = os.path.splitext(file_name_with_ext)

        print(f"Directory: {dir_name}")
        print(f"Filename without extension: {file_name}")

        try:
            files_in_directory = os.listdir(dir_name)
        except Exception as e:
            print(f"Error listing directory: {e}")
            return

        print(f"Files in directory: {files_in_directory}")

        files_to_move = [f for f in files_in_directory if os.path.splitext(f)[0] == file_name]

        print(f"Files to move: {files_to_move}")

        if files_to_move:
            new_dir = os.path.join(dir_name, "moved")
            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
                print(f"New directory created: {new_dir}")

            for f in files_to_move:
                try:
                    shutil.move(os.path.join(dir_name, f), os.path.join(new_dir, f))
                    print(f"Moved: {os.path.join(dir_name, f)} to {os.path.join(new_dir, f)}")
                except Exception as e:
                    print(f"Error moving {os.path.join(dir_name, f)}: {e}")

            file_with_suffix = file_name + "_1" + ".mkv"
            path_with_suffix = os.path.join(dir_name, file_with_suffix)

            if os.path.exists(path_with_suffix):
                try:
                    os.rename(path_with_suffix, os.path.join(dir_name, file_name_with_ext))
                    print(f"Renamed: {path_with_suffix} to {os.path.join(dir_name, file_name_with_ext)}")
                except Exception as e:
                    print(f"Error renaming {path_with_suffix}: {e}")
            else:
                print(f"File with _1 suffix not found: {path_with_suffix}")

    @staticmethod
    def get_probe(file):
        return ffmpeg.probe(file)

    def clear_dicts(self):
        self.mapper_s.clear()
        self.mapper_a.clear()
        self.metadata.clear()
        self.disposition.clear()

    def print_stream_info(self, file_path):

        probe = self.get_probe(file=file_path)
        filename = probe["format"]["filename"]

        print(filename)
        print()

        streams_df = pd.json_normalize(probe['streams'])

        print(streams_df.to_string())

        print()

    def print_summary(self, old, new, ffmpeg_command):

        print(f"Original File:")
        self.print_stream_info(old)
        print(f"New File:")
        self.print_stream_info(new)

        print("ffmpeg command:")
        print(ffmpeg_command)

    def get_probe_df(self, file):

        probe = ffmpeg.probe(file)

        streams_df = pd.json_normalize(probe['streams'])

        streams_df.sort_values(by='codec_type', inplace=True)
        streams_df.sort_index(inplace=True)

        if 'tags.language' in streams_df.columns:
            streams_df['tags.language'] = streams_df['tags.language'].replace({
                'de': 'ger',
                'deu': 'ger',
                'en': 'eng',
                'jap': 'jpn',
                'ja': 'jpn'
            })
            # streams_df['tags.language'] = streams_df['tags.language'].replace('deu', 'ger')
            streams_df['tags.language'].fillna(self.nan_language, inplace=True)

        return streams_df

    def get_disposition(self):

        for i in range(len(self.mapper_a)):
            self.disposition[f'disposition:a:{i}'] = 'default' if i == 0 else '0'

        for i in range(len(self.mapper_s)):
            self.disposition[f'disposition:s:{i}'] = 'default' if i == 0 else '0'

    def map_audio_streams(self, audio_streams: pd.DataFrame, input_stream):

        for language in self.a_language_priority:
            language_streams = audio_streams[audio_streams['tags.language'].str.contains(language, na=False)]

            if not language_streams.empty:
                index = language_streams.index[0]

                for codec in self.a_codec_priority:

                    if codec == "pcm_s16be":
                        codec = "pcm"

                    if self.convert_audio:
                        for old_codec, new_dict in self.convert_audio.items():
                            new_format = new_dict["format"]
                            new_bitrate = new_dict["bitrate"]

                            if codec == new_format:
                                self.mapper_a.append(input_stream[f"a:{index}"])
                                current_index = len(self.mapper_a) - 1

                                self.metadata[f"c:a:{current_index}"] = new_format
                                self.metadata[f"b:a:{current_index}"] = new_bitrate

                                self.metadata[f"metadata:s:a:{current_index}"] = [
                                    f'title={language.upper()} {new_format}',
                                    f'language={language}']

                            if new_dict["add"]:
                                if codec == old_codec:
                                    self.mapper_a.append(input_stream[f"a:{index}"])
                                    current_index = len(self.mapper_a) - 1

                                    self.metadata[f"metadata:s:a:{current_index}"] = [
                                        f'title={language.upper()} {codec}',
                                        f'language={language}']

                    else:
                        lang_codec_streams = language_streams[language_streams['codec_name'] == codec]
                        for index in lang_codec_streams.index:
                            self.mapper_a.append(input_stream[f"a:{index}"])
                            current_index = len(self.mapper_a) - 1
                            self.metadata[f"metadata:s:a:{current_index}"] = [f'title={language.upper()} {codec}',
                                                                              f'language={language}']

    def map_subtitle_streams(self, subtitle_streams: pd.DataFrame, input_stream, srt_stream):

        for language in self.s_language_priority:
            language_streams = subtitle_streams[
                (subtitle_streams['tags.language'].str.contains(language, na=False)) & (
                        subtitle_streams['disposition.forced'] == 0)]

            if not language_streams.empty or (self.add_srt["add"] and self.add_srt["language"] == language):
                prioritized_streams = pd.DataFrame()

                for codec in self.s_codec_priority:

                    if codec == "subrip" and srt_stream:
                        len_map_s = len(self.mapper_s)
                        self.mapper_s.append(srt_stream[f"s:{0}"])

                        self.metadata[f"metadata:s:s:{len_map_s}"] = [
                            f'title={language.upper()} {codec}',
                            f'language={language}']

                    else:

                        filtered_streams = subtitle_streams[subtitle_streams['codec_name'] == codec]
                        if not filtered_streams.empty:
                            if len(filtered_streams) > 1:
                                frames_columns = filtered_streams.filter(like='NUMBER_OF_FRAMES').columns

                                if not frames_columns.empty:
                                    filtered_streams[frames_columns[0]] = pd.to_numeric(filtered_streams[frames_columns[0]],
                                                                                        errors='coerce')
                                    sorted_streams = filtered_streams.sort_values(by=frames_columns[0], ascending=False)
                                    prioritized_streams = prioritized_streams.append(sorted_streams.iloc[0])
                                else:
                                    filtered_df = filtered_streams[~filtered_streams['tags.title'].str.contains('forced', case=False)]
                                    prioritized_streams = prioritized_streams.append(filtered_df.iloc[0])
                                    print(f"Two identical {codec} subtitles? Will chose the first {codec} stream")
                            else:
                                prioritized_streams = prioritized_streams.append(filtered_streams)

                            for index in prioritized_streams.index:

                                self.mapper_s.append(input_stream[f"s:{index}"])

                                if codec == "hdmv_pgs_subtitle":
                                    codec = "pgs"

                                self.metadata[f"metadata:s:s:{len(self.mapper_s)-1}"] = [
                                    f'title={language.upper()} {codec}',
                                    f'language={language}']

    def manipulate_mkv(self):

        for file in self.files:

            input_stream = ffmpeg.input(file)

            output_file = self.create_output_path(file)

            video_title_name = f"{file}"

            probe_df = self.get_probe_df(file)

            srt_input_stream = None

            if self.add_srt["add"]:
                srt_file = self.create_srt_file_name(file)
                srt_input_stream = ffmpeg.input(srt_file)

            audio_df = probe_df[probe_df['codec_type'] == 'audio'].reset_index(drop=True)
            sub_df = probe_df[probe_df['codec_type'] == 'subtitle'].reset_index(drop=True)

            self.map_audio_streams(audio_df, input_stream)
            self.map_subtitle_streams(sub_df, input_stream, srt_input_stream)
            self.get_disposition()
            self.metadata['metadata:s:v:0'] = f"title={video_title_name}"

            mapped_input = self.mapper_a + self.mapper_s

            mapped_input.insert(0, input_stream["v:0"])

            output_ffmpeg = (

                ffmpeg
                    .output(
                    *mapped_input,
                    output_file,
                    vcodec="copy",
                    acodec="copy",
                    scodec="copy",
                    # ch_layout="5.1",
                    **{"max_interleave_delta": "0"},
                    **self.metadata,
                    **self.disposition

                )
            )

            output_ffmpeg.run()

            self.clear_dicts()

            self.print_summary(file, output_file, ffmpeg.get_args(output_ffmpeg))

            if self.move_completed_files:
                self.move_files_and_rename(file)


path = r""
# file or directory path

manipulator = Manipulator(file_path=path,

                          a_language_priority=["jpn", "ger", "eng"],
                          a_codec_priority=['aac', 'ac3', 'eac3', 'opus', 'pcm_s16be', 'dts'],

                          convert_audio={},
                          # example: will convert all dts audio streams to ac3 640k
                          # {"dts": {"add":False, "format": "ac3", "bitrate": "640k"}}
                          # if add is True it will not delete the dts streams

                          s_language_priority=["ger", "eng"],
                          s_codec_priority=['subrip', 'hdmv_pgs_subtitle','ass'],

                          add_srt={"add": True, "language": "ger"},

                          move_completed_files=False,
                          # will move processed files to a new dir and rename the completed file to the original name.
                          nan_language="ger"
                          # sometimes the language of subtitles or audio is not specified. Check before (with manipulate.print_stream_info(file))
                          # and then define it manually here. Will replace all NaN tags.language with "ger" for example
                          )


manipulator.manipulate_mkv()
