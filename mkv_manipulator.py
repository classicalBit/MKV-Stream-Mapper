from pathlib import Path
import ffmpeg
import pandas as pd
import os
import shutil


class Manipulator:
    def __init__(self, file_path, a_language_priority: list, s_language_priority: list,
                 a_codec_priority, s_codec_priority, add_srt: bool, convert_audio: dict, move_completed_files: bool):
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

        files_to_delete = [f for f in files_in_directory if os.path.splitext(f)[0] == file_name]

        print(f"Files to move: {files_to_delete}")

        if files_to_delete:
            new_dir = os.path.join(dir_name, "moved")
            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
                print(f"New directory created: {new_dir}")

            for f in files_to_delete:
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

    def print_stream_info(self, file_path):

        probe = self.get_probe(file=file_path)
        filename = probe["format"]["filename"]

        print(filename)
        print()

        streams_df = pd.json_normalize(probe['streams'])

        print(streams_df.to_string())

        print()

    @staticmethod
    def get_probe_df(file):

        probe = ffmpeg.probe(file)

        streams_df = pd.json_normalize(probe['streams'])

        streams_df.sort_values(by='codec_type', inplace=True)
        streams_df.sort_index(inplace=True)

        if 'tags.language' in streams_df.columns:
            streams_df['tags.language'] = streams_df['tags.language'].replace('deu', 'ger')

        return streams_df

    def order_audio_streams(self, audio_streams: pd.DataFrame):

        if len(audio_streams) == 1:
            ordered_audio_index = list(audio_streams.index)
            print("ordered audio index:", ordered_audio_index)
            return ordered_audio_index
        else:
            ordered_audio_index = []

            for language in self.a_language_priority:

                language_streams = audio_streams[audio_streams['tags.language'].str.contains(language, na=False)]

                for codec in self.a_codec_priority:
                    lang_codec_streams = language_streams[language_streams['codec_name'] == codec]
                    ordered_audio_index.extend(lang_codec_streams.index.tolist())

            return ordered_audio_index

    def get_metadata_audio(self, ordered_index_list: list, audio_streams: pd.DataFrame):

        audio_metadata_dict = {}

        for idx, count in enumerate(ordered_index_list):
            codec_name = audio_streams[audio_streams.index == count]['codec_name'].iloc[0]
            language = audio_streams[audio_streams.index == count]['tags.language'].iloc[0]

            if codec_name == "pcm_s16be":
                codec_name = "pcm"

            if self.convert_audio:
                for old_codec, sub_dict in self.convert_audio.items():
                    if codec_name == old_codec:
                        audio_metadata_dict[f"c:a:{idx}"] = self.convert_audio[codec_name]["format"]
                        audio_metadata_dict[f"b:a:{idx}"] = self.convert_audio[codec_name]["bitrate"]
                        codec_name = self.convert_audio[codec_name]["format"]

            audio_metadata_dict[f'metadata:s:a:{idx}'] = [f'title={language.upper()} {codec_name}',
                                                          f'language={language}']

            if idx == 0:
                audio_metadata_dict['disposition:a:0'] = 'default'
            else:
                audio_metadata_dict[f'disposition:a:{idx}'] = '0'

        return audio_metadata_dict

    def order_subtitle_streams(self, sub_streams: pd.DataFrame):

        if len(sub_streams) == 1:
            codec_type_count_list = list(sub_streams.index)
            return codec_type_count_list
        else:
            codec_type_count_list = []

            for language in self.s_language_priority:
                language_filtered_streams = sub_streams[
                    (sub_streams['tags.language'] == language) & (sub_streams['disposition.forced'] == 0)]
                prioritized_streams = self.prioritize_streams(language_filtered_streams)
                codec_type_count_list.extend(prioritized_streams.index.tolist())

        return codec_type_count_list

    def prioritize_streams(self, streams):
        prioritized_streams = pd.DataFrame()

        for codec in self.s_codec_priority:
            filtered_streams = streams[streams['codec_name'] == codec]
            if len(filtered_streams) > 1:

                frames_columns = filtered_streams.filter(like='NUMBER_OF_FRAMES').columns
                if not frames_columns.empty:
                    filtered_streams[frames_columns[0]] = pd.to_numeric(filtered_streams[frames_columns[0]],
                                                                        errors='coerce')
                    sorted_streams = filtered_streams.sort_values(by=frames_columns[0], ascending=False)
                    prioritized_streams = prioritized_streams.append(sorted_streams.iloc[0])
                else:
                    filtered_df = filtered_streams[~filtered_streams['tags.title'].str.contains('forced')]
                    prioritized_streams = prioritized_streams.append(filtered_df.iloc[0])
                    print(f"Two identical {codec} subtitles? Will chose the first {codec} stream")
            else:
                prioritized_streams = prioritized_streams.append(filtered_streams)

        return prioritized_streams

    @staticmethod
    def get_metadata_subtitle(ordered_index_list: list, sub_df: pd.DataFrame):

        sub_metadata_dict = {}

        for idx, count in enumerate(ordered_index_list):
            codec_name = sub_df[sub_df.index == count]['codec_name'].iloc[0]
            language = sub_df[sub_df.index == count]['tags.language'].iloc[0]

            if codec_name == "hdmv_pgs_subtitle":
                codec_name = "pgs"

            sub_metadata_dict[f'metadata:s:s:{idx}'] = [f'title={language.upper()} {codec_name}',
                                                        f'language={language}']
            if idx == 0:
                sub_metadata_dict['disposition:s:0'] = 'default'
            else:
                sub_metadata_dict[f'disposition:s:{idx}'] = '0'

        return sub_metadata_dict

    def manipulate_mkv(self):

        for file in self.files:

            input_stream = ffmpeg.input(file)
            video_title_name = f"{file}"
            video_stream = input_stream["v"]

            output_file = self.create_output_path(file)

            probe_df = self.get_probe_df(file)

            audio_df = probe_df[probe_df['codec_type'] == 'audio'].reset_index(drop=True)
            sub_df = probe_df[probe_df['codec_type'] == 'subtitle'].reset_index(drop=True)
            len_sub_df = len(sub_df)

            a_ordered_index_list = self.order_audio_streams(audio_df)
            ordered_audio_input_list = [input_stream[f"a:{i}"] for i in a_ordered_index_list]
            a_metadata_dict = self.get_metadata_audio(a_ordered_index_list, audio_df)

            if self.add_srt:
                srt_file = self.create_srt_file_name(file)
                srt_probe_df = self.get_probe_df(srt_file)
                srt_probe_df["tags.language"] = "ger"
                srt_probe_df["tags.title"] = "GER subrip"
                sub_df = pd.concat([sub_df, srt_probe_df], ignore_index=True)
                srt_input_stream = ffmpeg.input(srt_file)

                s_ordered_index_list = self.order_subtitle_streams(sub_df)
                ordered_sub_input_list = [input_stream[f"s:{i}"] for i in s_ordered_index_list if i < len_sub_df]
                insert_position = next((i for i, idx in enumerate(s_ordered_index_list) if idx >= len_sub_df), None)

                if insert_position is not None:
                    ordered_sub_input_list.insert(insert_position, srt_input_stream)
                else:
                    ordered_sub_input_list.append(srt_input_stream)

                s_metadata_dict = self.get_metadata_subtitle(s_ordered_index_list, sub_df)

            else:
                s_ordered_index_list = self.order_subtitle_streams(sub_df)
                ordered_sub_input_list = [input_stream[f"s:{i}"] for i in s_ordered_index_list]
                s_metadata_dict = self.get_metadata_subtitle(s_ordered_index_list, sub_df)

            output_ffmpeg = (
                ffmpeg
                    .output(
                    video_stream,
                    *ordered_audio_input_list,
                    *ordered_sub_input_list,
                    output_file,
                    vcodec="copy",
                    acodec="copy",
                    scodec="copy",
                    **{"max_interleave_delta": "0"},
                    **{'metadata:s:v:0': f"title={video_title_name}"},
                    **a_metadata_dict,
                    **s_metadata_dict,
                )
            )

            output_ffmpeg.run()

            self.print_stream_info(file)
            self.print_stream_info(output_file)

            if self.move_completed_files:
                self.move_files_and_rename(file)


path = r""
# can be either a file or a directory

manipulator = Manipulator(file_path=path,

                          a_language_priority=["jpn", "ger", "eng"],
                          a_codec_priority=['eac3', 'ac3', 'aac', 'opus', 'pcm_s16be', 'dts'],

                          s_language_priority=["ger", "eng"],
                          s_codec_priority=['ass', 'subrip', 'hdmv_pgs_subtitle'],

                          add_srt=True,

                          convert_audio={},
                          # {"dts": {"format": "ac3", "bitrate": "640k"}} # exp: will convert all dts audio streams to ac3 640k
                          move_completed_files=False
                          # will move completed file(s) to a new dir and rename the completed file to the original name
                          )

manipulator.manipulate_mkv()
