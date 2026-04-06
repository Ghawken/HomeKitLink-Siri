"""Class to hold all camera accessories."""
import asyncio
from datetime import timedelta
import logging
import os
import sys
from indigoffmpeg.core import IndigoFFmpeg, FFMPEG_STDERR
from homekit_audio_proxy import AudioProxy
from typing import Any
from HKutils import pid_is_alive
from HKutils import SimpleIntervalScheduler
import time as t
import datetime
from typing import Callable


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

from HKDevicesCamera import resolve_video_strategy

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

DOORBELL_SINGLE_PRESS = 0
DOORBELL_DOUBLE_PRESS = 1
DOORBELL_LONG_PRESS = 2


VIDEO_OUTPUT_COPY = (
    "-map {v_map} -an -sn -dn "
    "-c:v copy "
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&pkt_size={v_pkt_size}"
)


VIDEO_OUTPUT_TRANSCODE = (
    "-map {v_map} -an -sn -dn "
    "-c:v libx264 "
    "{v_profile}"
    "-bf 0 "
    "-preset ultrafast "
    "-tune zerolatency "
    "-pix_fmt yuv420p "
    "-color_range mpeg "
    "-g 15 "
    "-keyint_min 15 "
    "-r {fps} "
    "-b:v {v_max_bitrate}k -bufsize {v_bufsize}k -maxrate {v_max_bitrate}k "
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&pkt_size={v_pkt_size}"
)


AUDIO_OUTPUT = (
    "-map {a_map} -vn -sn -dn "
    "-c:a {a_encoder} "
    "{a_application}"
    "-af asetpts=N/SR/TB "
    "-ac 1 -ar {a_sample_rate}k "
    "-b:a {a_max_bitrate}k -bufsize {a_bufsize}k "
    "{a_frame_duration}"
    "-payload_type 110 "
    "-ssrc {a_ssrc} -f rtp "
    "rtp://127.0.0.1:{a_proxy_port}?pkt_size={a_pkt_size}"
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
AUDIO_PROXY = "audio_proxy"

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


class SecuritySpyCamera(HomeAccessory, PyhapCamera):
    """Generate a Camera accessory."""

    def __init__(self, driver, plugin, indigodeviceid, display_name, aid, config, *args, **kwargs):
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
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["BASELINE"],
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["MAIN"],
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["HIGH"],
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
                {"type": "OPUS", "samplerate": 16},
                {"type": "OPUS", "samplerate": 24},
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

        self.base_config = config

        super().__init__(
            options=options,
            driver=driver,
            plugin=plugin,
            indigodeviceid=indigodeviceid,
            name=display_name,
            aid=aid,
            config=config,
        )

        self.doorbellID = None
        self._char_motion_detected = None
        self.linked_motion_sensor = indigodeviceid

        if config["useMotionSensor"]:
            _LOGGER.debug("useMotionSensor Enabled, setting up callbacks")
            serv_motion = self.add_preload_service("MotionSensor")
            self.char_motion_detected = serv_motion.configure_char("MotionDetected", value=False)

        if "DoorBell_ID" in config:
            _LOGGER.debug("using DoorBell Setting up..")
            self._char_doorbell_detected = None
            self._char_doorbell_detected_switch = None
            self.doorbellID = int(config["DoorBell_ID"])
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
        _LOGGER.debug("Run called once for CAMERA MotionSensor, and/or Doorbell, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    async def start_stream(self, session_info, stream_config):
        """Start a new stream with the given configuration."""
        try:
            if self.plugin.debug7:
                _LOGGER.debug(
                    "[%s] Starting stream -SecuritySpy Cam- with the following parameters: %s",
                    session_info["id"],
                    stream_config,
                )

            self.base_config = stream_config
            input_source = self.config.get(CONF_STREAM_SOURCE)
            ffprobe_video = self.config.get("ffprobe_video")
            ffprobe_audio = self.config.get("ffprobe_audio")

            # --- Log ffprobe results if available ---
            if ffprobe_video:
                _LOGGER.debug(
                    "[%s] ffprobe video: codec=%s %sx%s@%sfps pix_fmt=%s profile=%s copy_safe=%s gop=%s/%s",
                    self.display_name,
                    ffprobe_video.get("codec"),
                    ffprobe_video.get("width"),
                    ffprobe_video.get("height"),
                    ffprobe_video.get("fps"),
                    ffprobe_video.get("pix_fmt"),
                    ffprobe_video.get("profile"),
                    ffprobe_video.get("copy_safe"),
                    ffprobe_video.get("gop_frames"),
                    ffprobe_video.get("gop_seconds"),
                )
                if ffprobe_video.get("codec") == "unknown":
                    _LOGGER.info(
                        "\n[%s] ffprobe could not identify the video codec in this stream.\n"
                        "This usually means the camera's RTSP sub-stream is not properly configured\n"
                        "(e.g. H.265 sub-streams are not supported over RTSP).\n"
                        "Check your SecuritySpy camera stream settings.\n",
                        self.display_name,
                    )
            else:
                _LOGGER.debug(
                    "[%s] No ffprobe data available — run 'Check Camera Stream Compatibility' menu item",
                    self.display_name,
                )

            if self.config[CONF_SUPPORT_AUDIO] and ffprobe_audio:
                if ffprobe_audio.get("present") is False or (
                    not ffprobe_audio.get("codec") and not ffprobe_audio.get("sample_rate")
                ):
                    _LOGGER.warning(
                        "[%s] Audio ENABLED but ffprobe found NO audio stream in source — expect errors",
                        self.display_name,
                    )
                else:
                    _LOGGER.debug(
                        "[%s] ffprobe audio: codec=%s rate=%s channels=%s",
                        self.display_name,
                        ffprobe_audio.get("codec"),
                        ffprobe_audio.get("sample_rate"),
                        ffprobe_audio.get("channels"),
                    )

            _LOGGER.debug(
                "[%s] HomeKit negotiated: width=%s height=%s v_max_bitrate=%s fps=%s",
                self.display_name,
                stream_config.get("width"),
                stream_config.get("height"),
                stream_config.get("v_max_bitrate"),
                self.config[CONF_MAX_FPS],
            )

            # ============================================================
            # Resolve copy vs transcode
            # ============================================================
            strategy = resolve_video_strategy(
                ffprobe_video=ffprobe_video,
                video_codec_cfg=self.config[CONF_VIDEO_CODEC],
                stream_width=stream_config.get("width", 0),
                stream_height=stream_config.get("height", 0),
                max_width=self.config[CONF_MAX_WIDTH],
                max_height=self.config[CONF_MAX_HEIGHT],
            )

            # Log warnings from strategy
            for w in strategy["warnings"]:
                _LOGGER.warning("[%s] %s", self.display_name, w)

            # ============================================================
            # Enforce minimum bitrate for transcode
            # ============================================================
            if not strategy["use_copy"]:
                min_br = strategy.get("min_bitrate_kbps", 0)
                actual_br = stream_config.get("v_max_bitrate", 0)
                if min_br > 0 and actual_br < min_br:
                    _LOGGER.info(
                        "[%s] HomeKit requested %dk bitrate but minimum for %sx%s transcode is %dk — overriding",
                        self.display_name, actual_br,
                        strategy["target_resolution"][0],
                        strategy["target_resolution"][1],
                        min_br,
                    )
                    stream_config["v_max_bitrate"] = min_br

            # Log the decision
            if strategy["use_copy"]:
                _LOGGER.info(
                    "[%s] Video: COPY passthrough (%sx%s %s)",
                    self.display_name,
                    strategy["source_resolution"][0],
                    strategy["source_resolution"][1],
                    strategy["source_codec"],
                )
            else:
                _LOGGER.info(
                    "[%s] Video: TRANSCODE %s %sx%s → libx264 %sx%s — %s",
                    self.display_name,
                    strategy["source_codec"],
                    strategy["source_resolution"][0],
                    strategy["source_resolution"][1],
                    strategy["target_resolution"][0],
                    strategy["target_resolution"][1],
                    ", ".join(strategy["reasons"]) if strategy["reasons"] else "user config",
                )

            # ============================================================
            # Build ffmpeg arguments
            # ============================================================
            extra_commands = self.config.get("start_commands_extra", "")

            video_profile = ""
            if not strategy["use_copy"]:
                video_profile = (
                    "-profile:v "
                    + VIDEO_PROFILE_NAMES[
                        int.from_bytes(stream_config["v_profile_id"], byteorder="big")
                    ]
                    + " "
                )

            audio_application = ""
            audio_frame_duration = ""

            if self.config[CONF_AUDIO_CODEC] == "libopus":
                audio_application = "-application lowdelay "
                opus_frame_duration = stream_config.get("a_packet_time", 20)
                valid_opus_durations = [2.5, 5, 10, 20, 40, 60, 80, 100, 120]
                if opus_frame_duration not in valid_opus_durations:
                    _LOGGER.debug(
                        "[%s] Requested frame duration %s not valid for Opus, using 20",
                        self.display_name,
                        opus_frame_duration,
                    )
                    opus_frame_duration = 20
                audio_frame_duration = f"-frame_duration {opus_frame_duration} "

            # --- Audio proxy ---
            audio_proxy: AudioProxy | None = None
            if self.config[CONF_SUPPORT_AUDIO]:
                target_clock = stream_config["a_sample_rate"] * 1000
                _LOGGER.debug(
                    "[%s] Creating AudioProxy: dest_addr=%s, dest_port=%s, "
                    "srtp_key_b64=%s, target_clock_rate=%s",
                    self.display_name,
                    stream_config["address"],
                    stream_config["a_port"],
                    stream_config["a_srtp_key"],
                    target_clock,
                )
                try:
                    audio_proxy = AudioProxy(
                        dest_addr=stream_config["address"],
                        dest_port=stream_config["a_port"],
                        srtp_key_b64=stream_config["a_srtp_key"],
                        target_clock_rate=target_clock,
                        python_path=os.path.join(sys.prefix, "bin", "python3"),
                    )
                    await audio_proxy.async_start()
                except Exception:
                    _LOGGER.exception(
                        "[%s] AudioProxy raised an exception during start",
                        self.display_name,
                    )
                    audio_proxy = None

                if audio_proxy and not audio_proxy.local_port:
                    stderr_output = ""
                    if audio_proxy._process and audio_proxy._process.stderr:
                        try:
                            raw = await asyncio.wait_for(
                                audio_proxy._process.stderr.read(), timeout=2.0
                            )
                            stderr_output = raw.decode(errors="replace").strip()
                        except Exception:
                            pass
                    if not stderr_output and audio_proxy._process:
                        _LOGGER.error(
                            "[%s] Audio proxy failed — local_port=%s, returncode=%s, pid=%s (no stderr captured)",
                            self.display_name,
                            audio_proxy.local_port,
                            audio_proxy._process.returncode,
                            audio_proxy._process.pid,
                        )
                    else:
                        _LOGGER.error(
                            "[%s] Audio proxy failed — local_port=%s, subprocess stderr: %s",
                            self.display_name,
                            audio_proxy.local_port,
                            stderr_output or "(empty)",
                        )
                    await audio_proxy.async_stop()
                    audio_proxy = None
                elif audio_proxy:
                    _LOGGER.debug(
                        "[%s] AudioProxy started on local port %s",
                        self.display_name,
                        audio_proxy.local_port,
                    )

            # ============================================================
            # Build output_vars and format templates
            # ============================================================
            output_vars = stream_config.copy()
            output_vars.update(
                {
                    "v_profile": video_profile,
                    "v_bufsize": stream_config["v_max_bitrate"] * 4,
                    "v_map": self.config[CONF_VIDEO_MAP],
                    "fps": self.config[CONF_MAX_FPS],
                    "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                    "v_codec": self.config[CONF_VIDEO_CODEC],
                    "v_scale": strategy["v_scale"],
                    "a_bufsize": stream_config["a_max_bitrate"] * 4,
                    "a_map": self.config[CONF_AUDIO_MAP],
                    "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                    "a_encoder": self.config[CONF_AUDIO_CODEC],
                    "a_application": audio_application,
                    "a_frame_duration": audio_frame_duration,
                    "a_proxy_port": audio_proxy.local_port if audio_proxy else 0,
                }
            )

            if strategy["use_copy"]:
                output = VIDEO_OUTPUT_COPY.format(**output_vars)
            else:
                output = VIDEO_OUTPUT_TRANSCODE.format(**output_vars)

            if self.config[CONF_SUPPORT_AUDIO]:
                output = output + " " + AUDIO_OUTPUT.format(**output_vars)

            _LOGGER.debug("FFmpeg output settings: %s", output)

            # ============================================================
            # Build input source
            # ============================================================
            if strategy["input_extra"]:
                # HEVC or other codecs needing larger probe
                input_source = strategy["input_extra"] + "-rtsp_transport tcp -i " + input_source
            else:
                input_source = "-rtsp_transport tcp -i " + input_source

            _LOGGER.debug("INPUT SOURCE: %s", input_source)

            # ============================================================
            # Launch ffmpeg
            # ============================================================
            stream = IndigoFFmpeg(f"{str(self.plugin.ffmpeg_command_line)}")
            extra_cmd_toadd = "-hide_banner -nostats " + str(extra_commands)
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
                if audio_proxy:
                    await audio_proxy.async_stop()
                return False

            _LOGGER.info(
                "[%s] Started video stream process - PID %d",
                session_info["id"],
                stream.process.pid,
            )
            self.plugin.ffmpeg_lastCommand = []
            try:
                self.plugin.ffmpeg_lastCommand.insert(0, f"{str(self.plugin.ffmpeg_command_line)}")
                self.plugin.ffmpeg_lastCommand.extend(input_source.split())
                self.plugin.ffmpeg_lastCommand.extend(output.split())
                self.plugin.ffmpeg_lastCommand.extend(extra_cmd_toadd.split())
            except:
                _LOGGER.debug(
                    "Error creating ffmpeg_lastCommand %s %s %s %s",
                    self.plugin.ffmpeg_command_line, input_source, output, extra_cmd_toadd,
                )

            session_info["stream"] = stream
            session_info[FFMPEG_PID] = stream.process.pid
            session_info[AUDIO_PROXY] = audio_proxy
            stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)

            async def watch_session():
                await self._async_ffmpeg_watch(session_info["id"])

            session_info[FFMPEG_LOGGER] = asyncio.create_task(
                self._async_log_stderr_stream(stderr_reader)
            )

            session_info[FFMPEG_WATCHER] = SimpleIntervalScheduler(
                watch_session,
                FFMPEG_WATCH_INTERVAL,
            )

            session_info[FFMPEG_WATCHER].start()
            _LOGGER.debug("Started Watcher for ffmpeg Stream.")

            return await self._async_ffmpeg_watch(session_info["id"])

        except:
            _LOGGER.exception("Start Stream Exception")

    async def _async_log_stderr_stream(
            self, stderr_reader: asyncio.StreamReader
    ) -> None:
        """Log output from ffmpeg."""
        if self.plugin.debug7:
            _LOGGER.debug("%s: ffmpeg: started", self.display_name)
        while True:
            line_bytes = await stderr_reader.readline()
            if line_bytes == b"":
                return
            # Decode bytes to string using UTF-8 encoding
            line = line_bytes.decode('utf-8').rstrip()
            if 'Output file does not contain any stream' in line:
                _LOGGER.info("'Output file does not contain stream' error noted for video stream playback. Often this means the stream does not have Audio and audio has been enabled.")
                _LOGGER.info("Would suggest unpublish Camera, check gone in Home app, and then republish with Audio Disabled.")
            elif any(err in line for err in (
                "Connection refused",
                "Connection timed out",
                "401 Unauthorized",
                "403 Forbidden",
                "404 Not Found",
                "Server returned",
                "HTTP error",
                "method DESCRIBE failed",
                "AVERROR_EXIT",
                "No route to host",
                "Network is unreachable",
            )):
                _LOGGER.error(
                    "[%s] ffmpeg stream error: %s",
                    self.display_name, line,
                )
            else:
                # Log the line from stderr or handle it differently
                if self.plugin.debug7:
                    _LOGGER.debug(f"{self.display_name}: ffmpeg: {line}")

    async def _async_ffmpeg_watch(self, session_id: str) -> bool:
        """Check to make sure ffmpeg is still running and cleanup if not."""
        if self.plugin.debug7:
            _LOGGER.debug("_async_ffmpeg_watch called")
        if session_id not in self.sessions:
            _LOGGER.debug("_async_ffmpeg_watch: session %s no longer exists, stopping watcher", session_id)
            return False
        ffmpeg_pid = self.sessions[session_id][FFMPEG_PID]
        if ffmpeg_pid is None:
            _LOGGER.debug("_async_ffmpeg_watch: session %s has no PID, stopping watcher", session_id)
            return False
        if pid_is_alive(ffmpeg_pid):
            if self.plugin.debug7:
                _LOGGER.debug(f"_async_ffmpeg_watch, PID {ffmpeg_pid} appears alive.  Returning.")
            return True

        _LOGGER.warning("Streaming process ended unexpectedly - PID %d", ffmpeg_pid)
        if FFMPEG_WATCHER in self.sessions[session_id]:
            await self.sessions[session_id][FFMPEG_WATCHER].stop()
            self.sessions[session_id].pop(FFMPEG_WATCHER)
        self._async_stop_ffmpeg_watch(session_id)
        if session_id in self.sessions and "stream_idx" in self.sessions[session_id]:
            self.set_streaming_available(self.sessions[session_id]["stream_idx"])
        return False

    def _async_stop_ffmpeg_watch(self, session_id: str) -> None:
        """Cleanup a streaming session after stopping."""
        try:
            if self.plugin.debug7:
                _LOGGER.debug(f"_async_stop_ffmpeg_watch called")
            self.sessions[session_id].pop(FFMPEG_LOGGER).cancel()
        except:
            _LOGGER.debug(f"Exception in async stop ffmpeg stream", exc_info=True)

    async def reconfigure_stream(self, session_info, stream_config):
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        if self.plugin.debug7:
            _LOGGER.debug('RECONFIG STREAM CALLED: Interesting may be options for managing later\nSession Info {}\n\nStream Config\n{}\n'.format(session_info, stream_config))
        session_id = session_info["id"]
        return True

    async def stop_stream(self, session_info: dict[str, Any]) -> None:
        """Stop the stream for the given ``session_id``."""
        if self.plugin.debug7:
            _LOGGER.debug(f"*** stop_stream called")
        session_id = session_info["id"]
        if proxy := session_info.pop(AUDIO_PROXY, None):
            await proxy.async_stop()
        if not (stream := session_info.get("stream")):
            _LOGGER.debug("No stream for session ID %s", session_id)
            return
        else:
            if self.plugin.debug7:
                _LOGGER.debug(f"Stream {stream=}")
        if FFMPEG_WATCHER in self.sessions[session_id]:
            await self.sessions[session_id][FFMPEG_WATCHER].stop()
            self.sessions[session_id].pop(FFMPEG_WATCHER)
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
        try:
            debug_function = False
            if self.plugin.debug7:
                debug_function = True
            if "SS_name" in self.config:
                camname = self.config["SS_name"]
                if "image-width" in image_size:
                    width = image_size["image-width"]
                else:
                    width = 1380
                self.plugin.camera_snapShot_Requested_que.put((camname, width))
                path = self.plugin.cameraimagePath + "/" + camname + '.jpg'
            else:
                ## or default saved to plugin packages
                path = self.plugin.pluginPath + "/cameras/snapshot.jpg"

            if debug_function:
                _LOGGER.debug(f"Entering file read for: {path}")

            try:
                _LOGGER.debug("Before open()")
                with open(path, 'rb') as fp:
                    if debug_function:
                        _LOGGER.debug("After open(), before read()")
                    data = fp.read()
                    if debug_function:
                        _LOGGER.debug("After read()")
                        _LOGGER.debug(f"Data type: {type(data)}")
                        _LOGGER.debug(f"Data length: {len(data)}")
                        _LOGGER.debug(f"First 32 bytes: {data[:32]!r}")
                        _LOGGER.debug(f"get_snapshot returning bytes len={len(data)} header={data[:8]!r}")
                    return data
            except Exception as e:
                _LOGGER.debug(f"Exception during file read: {e}")
                raise

        except:
            _LOGGER.debug("Error in get snapshot:", exc_info=True)
            raise