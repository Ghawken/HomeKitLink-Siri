"""Class to hold all camera accessories."""
import asyncio
from datetime import timedelta
import logging
from indigoffmpeg.core import IndigoFFmpeg, FFMPEG_STDERR
from HKutils import pid_is_alive
import aiofiles
from typing import Any

import os
import time as t


from pyhap.camera import (
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
    Camera as PyhapCamera,
)

from pyhap.accessory import Accessory, Bridge

from pyhap.const import CATEGORY_CAMERA

from HomeKitDevices import HomeAccessory

from HKConstants import (
    CHAR_MOTION_DETECTED,
    CHAR_MUTE,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_LINKED_DOORBELL_SENSOR,
    CONF_LINKED_MOTION_SENSOR,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_STREAM_ADDRESS,
    CONF_STREAM_COUNT,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    CONF_VIDEO_MAP,
    CONF_VIDEO_PACKET_SIZE,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_MAP,
    DEFAULT_AUDIO_PACKET_SIZE,
    DEFAULT_MAX_FPS,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_STREAM_COUNT,
    DEFAULT_SUPPORT_AUDIO,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MAP,
    DEFAULT_VIDEO_PACKET_SIZE,
    DEFAULT_STREAM_SOURCE,
    SERV_DOORBELL,
    SERV_MOTION_SENSOR,
    SERV_SPEAKER,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
)


_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

DOORBELL_SINGLE_PRESS = 0
DOORBELL_DOUBLE_PRESS = 1
DOORBELL_LONG_PRESS = 2

VIDEO_OUTPUT = (
    "-map {v_map} -an -sn -dn "
    "-c:v {v_codec} "
  #   "{v_profile}" 
 #  "-preset ultrafast "
  #  "-tune zerolatency "
    "-bf 0 "
    "-pix_fmt yuv420p "
     "-color_range mpeg "
    "-f rawvideo "
  #  "-tune zerolatency -pix_fmt yuv420p "
    "-r {fps} "
    "-b:v {v_max_bitrate}k -bufsize {v_bufsize}k -maxrate {v_max_bitrate}k "
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&"
    "localrtcpport={v_port}&pkt_size={v_pkt_size}"
)

# VIDEO_OUTPUT2 = (
#     "-map {v_map} "  #-an "
#     "-vcodec {v_codec} "
#   #  "-f rawvideo "
#     "{v_profile}"
#     "-pix_fmt yuv420p "
#     "-r {fps} "
#     "-f rawvideo "
#     "-b:v {v_max_bitrate}k -bufsize {v_bufsize}k -maxrate {v_max_bitrate}k "
#     "-payload_type 99 "
#     "-ssrc {v_ssrc} -f rtp "
#     "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
#     "srtp://{address}:{v_port}?rtcpport={v_port}&"
#     "localrtcpport={v_port}&pkt_size={v_pkt_size}"
# )

# AUDIO_OUTPUT2 = (
#     "-map {a_map} "#-vn "
#     "-strict -2 "
#     "-acodec {a_encoder} "
#     "-flags:a +global_header "
#   #  "{a_application}"
#     "-ac 1 -ar 24k " #-ar {a_sample_rate}k "
#     "-b:a 8k "#-bufsize 48k " # k{a_max_bitrate}k "#-bufsize {a_bufsize}k "
#     "-payload_type 110 "
#     "-ssrc {a_ssrc} -f rtp "
#     "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {a_srtp_key} "
#     "srtp://{address}:{a_port}?rtcpport={a_port}&"
#     "localrtcpport={a_port}&pkt_size=188"#{a_pkt_size}"
# )


AUDIO_OUTPUT = (
    "-map {a_map} -vn -sn -dn "
    "-c:a {a_encoder} "
    "{a_application}"
    '-profile:a aac_eld '
    '-flags +global_header ' 
    "-f null "
    "-ac 1 -ar {a_sample_rate}k "
    "-b:a {a_max_bitrate}k -bufsize {a_bufsize}k "
    "-payload_type 110 "
    "-ssrc {a_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {a_srtp_key} "
    "srtp://{address}:{a_port}?rtcpport={a_port}&"
    "localrtcpport={a_port}&pkt_size={a_pkt_size}"
)
SLOW_RESOLUTIONS = [
    (320, 180, 15),
    (320, 240, 15),
]

RESOLUTIONS = [
    (320, 180),
    (320, 240),
    (480, 270),
    (480, 360),
    (640, 360),
    (640, 480),
    (1024, 576),
    (1024, 768),
    (1280, 720),
    (1280, 960),
    (1920, 1080),
    (1600, 1200),
]

VIDEO_PROFILE_NAMES = ["baseline", "main", "high"]

FFMPEG_WATCH_INTERVAL = timedelta(seconds=5)
FFMPEG_LOGGER = "ffmpeg_logger"
FFMPEG_WATCHER = "ffmpeg_watcher"
FFMPEG_PID = "ffmpeg_pid"
SESSION_ID = "session_id"

CONFIG_DEFAULTS = {
    CONF_SUPPORT_AUDIO: DEFAULT_SUPPORT_AUDIO,
    CONF_MAX_WIDTH: DEFAULT_MAX_WIDTH,
    CONF_MAX_HEIGHT: DEFAULT_MAX_HEIGHT,
    CONF_MAX_FPS: DEFAULT_MAX_FPS,
    CONF_AUDIO_CODEC: DEFAULT_AUDIO_CODEC,
    CONF_AUDIO_MAP: DEFAULT_AUDIO_MAP,
    CONF_VIDEO_MAP: DEFAULT_VIDEO_MAP,
    CONF_VIDEO_CODEC: DEFAULT_VIDEO_CODEC,
    CONF_AUDIO_PACKET_SIZE: DEFAULT_AUDIO_PACKET_SIZE,
    CONF_VIDEO_PACKET_SIZE: DEFAULT_VIDEO_PACKET_SIZE,
    CONF_STREAM_COUNT: DEFAULT_STREAM_COUNT,
    CONF_STREAM_SOURCE: DEFAULT_STREAM_SOURCE
}


class SecuritySpyCamera(HomeAccessory,  PyhapCamera):
    """Generate a Camera accessory."""
   #def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid, config, *args, **kwargs):
        """Initialize a Camera accessory object."""

        self.plugin = plugin

        for config_key, conf in CONFIG_DEFAULTS.items():
            if config_key not in config:
                config[config_key] = conf

        max_fps = config[CONF_MAX_FPS]
        max_width = config[CONF_MAX_WIDTH]
        max_height = config[CONF_MAX_HEIGHT]

        resolutions = [
            (w, h, fps)
            for w, h, fps in SLOW_RESOLUTIONS
            if w <= max_width and h <= max_height and fps < max_fps
        ] + [
            (w, h, max_fps)
            for w, h in RESOLUTIONS
            if w <= max_width and h <= max_height
        ]

        video_options = {
            "codec": {
                "profiles": [
                  #  VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["BASELINE"],
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["MAIN"],
                  #  VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["HIGH"],
                ],
                "levels": [
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE3_1"],
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE3_2"],
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE4_0"],
                ],
            },
            "resolutions": resolutions,
        }
        audio_options = {
            "codecs": [
             #   {"type": "OPUS", "samplerate": 16},
              #  {"type": "OPUS", "samplerate": 24},
                {"type": "AAC-eld","samplerate":16}
            ]
        }

        stream_address = config.get(CONF_STREAM_ADDRESS, driver.state.address)

        options = {
            "video": video_options,
            "audio": audio_options,
            "address": stream_address,
            "srtp": True,
            "stream_count": config[CONF_STREAM_COUNT],
        }

    #   def __init__(self, driver, plugin, indigodeviceid, display_name, aid):  # self, *args, **kwargs):
        super().__init__(
            options=options,
            driver=driver,
            plugin=plugin,
            indigodeviceid=indigodeviceid,
            name=display_name,
            aid=aid,
            config=config,
        )
        ## Use BlueIris Camera State - remember this class in BlueIris Camera only reallly now...
        ## Use the Motion state of Device as linked Motion Sensor for camera.
        ## TODO Likely add checkbox to enable/disable linked motion otherwise notifications all the time annoying

        self.doorbellID = None
        self._char_motion_detected = None
        self.linked_motion_sensor = indigodeviceid  ## indigodevice.Id for moment use indigodeviceid.. potential to change to another device later
        if config["useMotionSensor"]:
            _LOGGER.debug("useMotionSensor Enabled, setting up callbacks")
            serv_motion = self.add_preload_service("MotionSensor")
            self.char_motion_detected = serv_motion.configure_char("MotionDetected", value=False) #), getter_callback=self.get_bulb )
            #oops...self.char_motion_detected.setter_callback = self._set_chars

        if "DoorBell_ID" in config:  ## now always true
            _LOGGER.debug("using DoorBell Setting up..")
            self._char_doorbell_detected = None
            self._char_doorbell_detected_switch = None
            self.doorbellID = int(config["DoorBell_ID"] )  ## self
            serv_doorbell = self.add_preload_service("Doorbell")

            self._char_doorbell_detected = serv_doorbell.configure_char(
                "ProgrammableSwitchEvent",
                value=0,
            )
            serv_stateless_switch = self.add_preload_service(
                "StatelessProgrammableSwitch"
            )
            self._char_doorbell_detected_switch = (
                serv_stateless_switch.configure_char(
                    "ProgrammableSwitchEvent",
                    value=0,
                    valid_values={"SinglePress": 0},
                )
            )
            serv_speaker = self.add_preload_service("Speaker")
            serv_speaker.configure_char("Mute", value=0)

    async def run(self):
        #if self.plugin.debug6:
        _LOGGER.debug("Run called once for CAMERA MotionSensor, and/or Doorbell, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)
        #?#await super().run()
    # _LOGGER.info("In Camera:\nOptions:\n{}\nConfig{}\n".format(options, config))

    async def start_stream(self, session_info, stream_config):
        """Start a new stream with the given configuration."""
        try:
            _LOGGER.debug(
                "[%s] Starting stream -SecuritySpy Cam- with the following parameters: %s",
                session_info["id"],
                stream_config
            )

            input_source = self.config.get(CONF_STREAM_SOURCE)
            extra_commands = self.config.get("start_commands_extra", None)
            _LOGGER.debug("Input Source\n{}".format(input_source))
            video_profile = ""
            if self.config[CONF_VIDEO_CODEC] != "copy":
                video_profile = (
                    "-profile:v "
                    + VIDEO_PROFILE_NAMES[
                        int.from_bytes(stream_config["v_profile_id"], byteorder="big")
                    ]
                    + " "
                )

            audio_application = ""
            if self.config[CONF_AUDIO_CODEC] == "libopus":
                audio_application = "-application lowdelay "

           # stream_config["v_max_bitrate"] = self.config["v_max_bitrate"]
            output_vars = stream_config.copy()
            output_vars.update(
                {
                    "v_profile": video_profile,
                #    "v_max_bitrate" : stream_config["v_max_bitrate"] *4,
                    "v_bufsize": stream_config["v_max_bitrate"] * 8,
                    "v_map": self.config[CONF_VIDEO_MAP],
                    "fps": self.config[CONF_MAX_FPS],
                    "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                    "v_codec": self.config[CONF_VIDEO_CODEC],
                    "a_bufsize": stream_config["a_max_bitrate"] * 4,
                    "a_map": self.config[CONF_AUDIO_MAP],
                    "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                    "a_encoder": self.config[CONF_AUDIO_CODEC],
                    "a_application": audio_application,
                }
            )
            output = VIDEO_OUTPUT.format(**output_vars)



            if self.config[CONF_SUPPORT_AUDIO]:
                output = output + " " + AUDIO_OUTPUT.format(**output_vars)

            _LOGGER.debug(f"FFmpeg output_vars {output_vars}")
            _LOGGER.debug("FFmpeg output settings: %s", output)

            _LOGGER.debug(
               '[%s] Starting stream with the following parameters: %s',
               session_info['id'],
               stream_config
            )

            input_source =  input_source #+ "&kbps="+str(output_vars["v_max_bitrate"]) #' ##&h="+str(stream_config["height"])+"&fps="+str(output_vars["fps"])

            input_source = "-rtsp_transport tcp -i " + input_source

            stream = IndigoFFmpeg(f"{str(self.plugin.ffmpeg_command_line)}")
            extra_cmd_toadd = "-hide_banner -nostats "+str(extra_commands)
            opened = await stream.open(
                cmd=[],
                input_source=input_source,
                output=output,
                extra_cmd=extra_cmd_toadd,
                stderr_pipe=True,
                stdout_pipe=False,
            )
            if not opened:
                _LOGGER.error("Failed to open ffmpeg stream")
                return False

            _LOGGER.info(
                "[%s] Started video stream process - PID %d",
                session_info["id"],
                stream.process.pid,
            )

            try:
                self.plugin.ffmpeg_lastCommand.insert(0,f"{str(self.plugin.ffmpeg_command_line)}" )
                self.plugin.ffmpeg_lastCommand.extend(input_source.split())
                self.plugin.ffmpeg_lastCommand.extend(output.split())
                self.plugin.ffmpeg_lastCommand.extend(extra_cmd_toadd.split())
            except:
                _LOGGER.debug(f"Error creating ffmpeg_lastCommand {self.plugin.ffmpeg_command_line=} {input_source=} {output=} {extra_cmd_toadd=}")
                pass

            session_info["stream"] = stream
            session_info[FFMPEG_PID] = stream.process.pid

            stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)

            async def watch_session(_: Any) -> None:
                await self._async_ffmpeg_watch(session_info["id"])

            session_info[FFMPEG_LOGGER] = asyncio.create_task(
                self._async_log_stderr_stream(stderr_reader)
            )

            return await self._async_ffmpeg_watch(session_info["id"])
        except:
            _LOGGER.exception("Start Stream Exception")

    async def _async_log_stderr_stream(
            self, stderr_reader: asyncio.StreamReader
    ) -> None:
        """Log output from ffmpeg."""
        _LOGGER.debug("%s: ffmpeg: started", self.display_name)
        while True:
            line = await stderr_reader.readline()
            if line == b"":
                return
            _LOGGER.debug("%s: ffmpeg: %s", self.display_name, line.rstrip())

    async def _async_ffmpeg_watch(self, session_id: str) -> bool:
        """Check to make sure ffmpeg is still running and cleanup if not."""
        ffmpeg_pid = self.sessions[session_id][FFMPEG_PID]
        if pid_is_alive(ffmpeg_pid):
            return True

        _LOGGER.warning("Streaming process ended unexpectedly - PID %d", ffmpeg_pid)
        self._async_stop_ffmpeg_watch(session_id)
        self.set_streaming_available(self.sessions[session_id]["stream_idx"])
        return False

    def _async_stop_ffmpeg_watch(self, session_id: str) -> None:
        """Cleanup a streaming session after stopping."""
        if FFMPEG_WATCHER not in self.sessions[session_id]:
            return
        self.sessions[session_id].pop(FFMPEG_WATCHER)()
        self.sessions[session_id].pop(FFMPEG_LOGGER).cancel()

    async def reconfigure_stream(self, session_info, stream_config):
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        _LOGGER.debug('RECONFIG STREAM CALLED: Interesting may be options for managing later\nSession Info {}\n\nStream Config\n{}\n'.format(session_info,stream_config))
        return True

    def async_stop(self) -> None:
        """Stop any streams when the accessory is stopped."""
        for session_info in self.sessions.values():
            self.hass.async_create_background_task(
                self.stop_stream(session_info), "homekit.camera-stop-stream"
            )
        super().async_stop()

    async def stop_stream(self, session_info: dict[str, Any]) -> None:
        """Stop the stream for the given ``session_id``."""
        session_id = session_info["id"]
        if not (stream := session_info.get("stream")):
            _LOGGER.debug("No stream for session ID %s", session_id)
            return

        self._async_stop_ffmpeg_watch(session_id)

        if not pid_is_alive(stream.process.pid):
            _LOGGER.info("[%s] Stream already stopped", session_id)
            return

        for shutdown_method in ("close", "kill"):
            _LOGGER.info("[%s] %s video stream", session_id, shutdown_method)
            try:
                await getattr(stream, shutdown_method)()
                return
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "[%s] Failed to %s stream", session_id, shutdown_method
                )

    async def stop(self):
        """Stop any streams when the accessory is stopped."""
        for session_info in self.sessions.values():
            asyncio.create_task(self.stop_stream(session_info))
        await super().stop()

    def get_snapshot(self, image_size):  # pylint: disable=unused-argument, no-self-use
    #async def async_get_snapshot(self, image_size):
        try:

            if "SS_name" in self.config:
                camname = self.config["SS_name"]
                #_LOGGER.info("Get_Snapshot Config: called for this camera Name {}".format(camname ))
                if "image-width" in image_size:
                    width = image_size["image-width"]
                else:
                    width = 1380
                self.plugin.camera_snapShot_Requested_que.put((camname,width))  # que a tuple..
                #_LOGGER.info("Image Size:{}".format(image_size))
                path = self.plugin.cameraimagePath+ "/"+camname+'.jpg'
            else:
                ## or default saved to plugin packages
                path = self.plugin.pluginPath + "/cameras/snapshot.jpg"
            #_LOGGER.info("Path{}".format(path))

            # async with aiofiles.open(path, mode='rb') as f:
            #     contents = await f.read()
            # return contents

            # bit of holiday and see issue needs a timer here
            # block at the IO part
            with open(path, 'rb') as fp:
                 return fp.read()

        except:
            _LOGGER.exception("{}")

    # the below craps out CPU usage enormously upto 50%
    #  Disabling resolves on my current testing.
    #  I would guess is the none async nature and probably hangs cycles
    # other implementations use a async def async_get_snapshot oddly - not in main class unless modified..
    # okay - pyhap/hap_handler.py - defines 2 options async_get_snapshot or get_snapshot so both okay..
    # should try former with error handling and see if major exceptions causing CPU usage 1st off.
    # def get_snapshot(self, image_size):  # pylint: disable=unused-argument, no-self-use
    #     """Return a jpeg of a snapshot from the camera.
    #     Overwrite to implement getting snapshots from your camera.
    #     :param image_size: ``dict`` describing the requested image size. Contains the
    #         keys "image-width" and "image-height"
    #     """
    #     try:
    #
    #         if "BI_name" in self.config:
    #             camname = self.config["BI_name"]
    #             #_LOGGER.info("Get_Snapshot Config: called for this camera Name {}".format(camname ))
    #             if "image-width" in image_size:
    #                 width = image_size["image-width"]
    #             else:
    #                 width = 1380
    #             self.plugin.camera_snapShot_Requested_que.put((camname,width))  # que a tuple..
    #             #_LOGGER.info("Image Size:{}".format(image_size))
    #             path = self.plugin.pluginPath+ '/cameras/'+camname+'.jpg'
    #         else:
    #             path = self.plugin.pluginPath + "/cameras/snapshot.jpg"
    #         #_LOGGER.info("Path{}".format(path))
    #
    #
    #         with open(path, 'rb') as fp:
    #             return fp.read()
    #
    #     except:
    #         _LOGGER.error("{}")
