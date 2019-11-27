#!/usr/bin/env python3
import logging
from abc import ABCMeta, abstractmethod

from lib.config import Config


class AVSource(object, metaclass=ABCMeta):

    def __init__(self, class_name, name,
                 has_audio=True, has_video=True,
                 num_streams=None, show_no_signal=False):
        self.log = logging.getLogger("%s[%s]" % (class_name, name))

        assert has_audio or has_video

        self.class_name = class_name
        self.name = name
        self.has_audio = has_audio
        self.has_video = has_video
        if name == "blinder":
            self.audio_streams = Config.getBlinderAudioStreams()
        else:
            self.audio_streams = Config.getAudioStreams()
        self.show_no_signal = show_no_signal
        self.inputSink = None
        self.bin = ""

    @abstractmethod
    def __str__(self):
        raise NotImplementedError(
            '__str__ not implemented for this source')

    def attach(self, pipeline):
        if self.show_no_signal and Config.getNoSignal():
            if self.has_video:
                self.inputSink = pipeline.get_by_name(
                    'compositor-{}'.format(self.name)).get_static_pad('sink_1')

    def build_pipeline(self):
        self.bin = """
            bin.(
                name={class_name}-{name}
            """.format(class_name=self.class_name, name=self.name)

        self.bin += self.build_source()

        if self.internal_audio_channels():
            audioport = self.build_audioport()
            if audioport:
                self.bin += """
                    {audioport}
                    ! tee
                        name=source-audio-{name}
                    """.format(
                    audioport=audioport,
                    name=self.name
                )
                for stream in self.audio_streams.get_stream_names(self.name):
                    self.bin += """
                        source-audio-{name}.
                        ! audiomixmatrix
                            name=audiomixmatrix-{stream}
                            in-channels={in_channels}
                            out-channels={out_channels}
                            matrix="{matrix}"
                        ! {acaps}
                        ! tee
                            name=audio-{stream}
                        """.format(
                        in_channels=self.internal_audio_channels(),
                        out_channels=self.audio_streams.num_channels(),
                        matrix=str(self.audio_streams.matrix(self.name, stream,
                                                             self.get_valid_channel_numbers())
                                   ).replace("[", "<").replace("]", ">"),
                        acaps=Config.getAudioCaps(),
                        stream=stream,
                        name=self.name
                    )

        if self.has_video:
            if self.show_no_signal and Config.getNoSignal():
                video = """
                    videotestsrc
                        name=canvas-{name}
                        pattern=black
                    ! textoverlay
                        name=nosignal-{name}
                        text=\"NO SIGNAL\"
                        valignment=center
                        halignment=center
                        font-desc="Roboto Bold, 20"
                    ! {vcaps}
                    ! compositor-{name}.

                    {videoport}
                    ! {vcaps}
                    ! compositor-{name}.

                    compositor
                        name=compositor-{name}
                    ! tee
                        name=video-{name}"""
            else:
                video = """
                    {videoport}
                    ! {vcaps}
                    ! tee
                        name=video-{name}"""
            self.bin += video.format(
                videoport=self.build_videoport(),
                name=self.name,
                vcaps=Config.getVideoCaps()
            )
        self.bin += """
                    )
                    """

        self.bin = self.bin

    def build_source(self):
        return ""

    def build_deinterlacer(self):
        source_mode = Config.getSourceScan(self.name)

        if source_mode == "interlaced":
            return "videoconvert ! yadif mode=interlaced"
        elif source_mode == "psf":
            return "capssetter " \
                   "caps=video/x-raw,interlace-mode=progressive"
        elif source_mode == "progressive":
            return None
        else:
            raise RuntimeError(
                "Unknown Deinterlace-Mode on source {} configured: {}".
                format(self.name, source_mode))

    def video_channels(self):
        return 1 if self.has_video else 0

    def audio_channels(self):
        return self.audio_streams.num_channels(self.name) if self.has_audio else 0

    def internal_audio_channels(self):
        return self.audio_streams.num_channels(self.name, self.get_valid_channel_numbers()) if self.has_audio else 0

    def get_valid_channel_numbers(self):
        return [x for x in range(1, 255)]

    def num_connections(self):
        return 0

    def is_input(self):
        return True

    def section(self):
        return 'source.{}'.format(self.name)

    @abstractmethod
    def port(self):
        assert False, "port() not implemented in %s" % self.name

    def build_audioport(self):
        assert False, "build_audioport() not implemented in %s" % self.name

    def build_videoport(self):
        assert False, "build_videoport() not implemented in %s" % self.name
