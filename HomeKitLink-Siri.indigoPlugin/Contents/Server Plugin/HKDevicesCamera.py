"""Class to hold all camera accessories."""
import asyncio
from datetime import timedelta
import logging

from scipy.stats import false_discovery_control

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

import os
import sys
from HomeKitDevices import HomeAccessory

from pyhap.accessory import Accessory, Bridge

from pyhap.const import CATEGORY_CAMERA

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


VIDEO_OUTPUT_base = (
    "-map {v_map} -an -sn -dn "
    "-c:v {v_codec} "
     "{v_profile}" 
    "-preset ultrafast "
    "-tune zerolatency "
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

VIDEO_OUTPUT_COPY = (
    "-map {v_map} -an -sn -dn "
    "-c:v copy "
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&pkt_size={v_pkt_size}"
)


VIDEO_OUTPUT = (
    "-map {v_map} -an -sn -dn "
    "-c:v {v_codec} "
     "{v_profile}" 
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&pkt_size={v_pkt_size}"
 #   "localrtcpport={v_port}&pkt_size={v_pkt_size}"
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
 #   "localrtcpport={v_port}&pkt_size={v_pkt_size}"
)


FFMPEG_WATCH_INTERVAL = timedelta(seconds=5)
FFMPEG_LOGGER = "ffmpeg_logger"
FFMPEG_WATCHER = "ffmpeg_watcher"
FFMPEG_PID = "ffmpeg_pid"
SESSION_ID = "session_id"

AUDIO_OUTPUT_aac = (
    "-map {a_map} -vn -sn -dn "
    "-c:a {a_encoder} "
    "{a_application}" 
    "-af asetpts=N/SR/TB "
    '-profile:a aac_eld '
    '-flags +global_header ' 
    "-af asetpts=N/SR/TB "
  #  "-f null "
    "-ac 1 -ar {a_sample_rate}k "
    "-b:a {a_max_bitrate}k -bufsize {a_bufsize}k "
    "{a_frame_duration}"
    "-payload_type 110 "
    "-ssrc {a_ssrc} -f rtp "
 #   "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {a_srtp_key} "
 #   "srtp://{address}:{a_port}?rtcpport={a_port}&"
 #   "localrtcpport={a_port}&pkt_size={a_pkt_size}"
    "rtp://127.0.0.1:{a_proxy_port}?pkt_size={a_pkt_size}"
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


def resolve_video_strategy(
        ffprobe_video: dict | None,
        video_codec_cfg: str,
        stream_width: int,
        stream_height: int,
        max_width: int,
        max_height: int,
) -> dict:
    """Decide whether to copy or transcode, and build any needed filters.

    This is a pure function — no side effects, no logging, no I/O.
    Call it from start_stream, from diagnostics, from tests, etc.

    Parameters
    ----------
    ffprobe_video : dict or None
        The ``cam["ffprobe_video"]`` dict produced by ``_run_ffprobe``.
        ``None`` means ffprobe was never run or failed entirely.
    video_codec_cfg : str
        The user's configured video codec, e.g. ``"copy"`` or ``"libx264"``.
    stream_width : int
        Width HomeKit requested for this stream session (from ``stream_config["width"]``).
    stream_height : int
        Height HomeKit requested for this stream session (from ``stream_config["height"]``).
    max_width : int
        Max width from camera config (``CONF_MAX_WIDTH``).
    max_height : int
        Max height from camera config (``CONF_MAX_HEIGHT``).

    Returns
    -------
    dict with keys:
        use_copy : bool
            True → use VIDEO_OUTPUT_COPY template.
            False → use VIDEO_OUTPUT_TRANSCODE template.
        reasons : list[str]
            Human-readable list of reasons for the decision.
            Empty when copy is chosen with no concerns.
        v_scale : str
            The ``-vf …`` scale/pad filter string for the transcode template.
            Empty string ``""`` when no scaling is needed or when copying.
        input_extra : str
            Extra input flags needed, e.g. larger probesize for HEVC.
            Empty string ``""`` when none needed.
        warnings : list[str]
            Non-fatal warnings to log (e.g. "no ffprobe data", "GOP borderline").
        source_codec : str
            The source codec name from ffprobe, or "unknown".
        source_resolution : tuple[int, int]
            (width, height) from ffprobe, or (0, 0).
        target_resolution : tuple[int, int]
            (width, height) that will be output. Same as source for copy,
            or the scaled size for transcode.
    """
    result = {
        "use_copy": False,
        "reasons": [],
        "v_scale": "",
        "input_extra": "",
        "warnings": [],
        "source_codec": "unknown",
        "source_resolution": (0, 0),
        "target_resolution": (0, 0),
        "min_bitrate_kbps": 0,  # NEW: suggested minimum bitrate for transcode
    }

    # -----------------------------------------------------------------
    # Fallback: no ffprobe data at all
    # -----------------------------------------------------------------
    if ffprobe_video is None:
        # No probe data — honour user config blindly, but warn
        result["use_copy"] = (video_codec_cfg == "copy")
        result["warnings"].append(
            f"No ffprobe data available — falling back to config video_codec='{video_codec_cfg}'. "
            "Run 'Check Camera Stream Compatibility' for reliable detection."
        )
        if not result["use_copy"]:
            result["reasons"].append("user config (no probe data)")
        return result

    # -----------------------------------------------------------------
    # Extract ffprobe fields
    # -----------------------------------------------------------------
    src_codec = ffprobe_video.get("codec", "unknown")
    src_w = ffprobe_video.get("width", 0)
    src_h = ffprobe_video.get("height", 0)
    copy_safe = ffprobe_video.get("copy_safe", False)
    gop_ok = ffprobe_video.get("gop_ok", True)
    gop_frames = ffprobe_video.get("gop_frames")
    gop_seconds = ffprobe_video.get("gop_seconds")
    pix_fmt = ffprobe_video.get("pix_fmt", "unknown")
    level = ffprobe_video.get("level", -1)
    profile = ffprobe_video.get("profile", "unknown")

    result["source_codec"] = src_codec
    result["source_resolution"] = (src_w, src_h)

    # -----------------------------------------------------------------
    # Decision: can we copy?
    # -----------------------------------------------------------------
    # Start from user preference
    wants_copy = (video_codec_cfg == "copy")

    if wants_copy and copy_safe and gop_ok:
        # ✅ Best case: user wants copy, stream supports it, GOP is fine
        result["use_copy"] = True
        result["target_resolution"] = (src_w, src_h)
        return result

    # If we get here, we're transcoding. Collect reasons why.
    result["use_copy"] = False

    if not wants_copy:
        # User explicitly chose to transcode
        result["reasons"].append(f"user config video_codec='{video_codec_cfg}'")
    else:
        # User wanted copy but we can't honour it
        if src_codec != "h264":
            result["reasons"].append(f"codec={src_codec} (not H.264, must transcode)")
            # HEVC needs larger probesize to find keyframes reliably
            if src_codec == "hevc":
                result["input_extra"] = "-probesize 5000000 -analyzeduration 3000000 "
        if not copy_safe and src_codec == "h264":
            # H.264 but something else is wrong
            if pix_fmt != "yuv420p":
                result["reasons"].append(f"pix_fmt={pix_fmt} (HomeKit needs yuv420p)")
            if not (0 < level <= 40):
                result["reasons"].append(f"level={level} (HomeKit needs ≤4.0)")
            if profile in ("High 10", "High 4:2:2", "High 4:4:4 Predictive"):
                result["reasons"].append(f"profile={profile} (unsupported chroma/bit-depth)")
            if src_w <= 0 or src_h <= 0 or src_w % 2 != 0 or src_h % 2 != 0:
                result["reasons"].append(f"resolution={src_w}x{src_h} (odd or zero)")
        if not gop_ok:
            if gop_seconds is not None:
                result["reasons"].append(f"GOP={gop_seconds:.1f}s (too large, HomeKit needs ≤4s)")
            elif gop_frames is not None:
                result["reasons"].append(f"GOP={gop_frames}+ frames (too large)")
            else:
                result["reasons"].append("GOP could not be measured")

    # -----------------------------------------------------------------
    # Output resolution and minimum bitrate
    # -----------------------------------------------------------------
    # Resolution scaling is intentionally disabled. Both -vf scale= and
    # -s WxH produce valid H.264 output that plays correctly in local
    # files, but HomeKit fails to render the scaled stream via SRTP.
    # The root cause is unknown — the encoded output, profile, level,
    # bitrate, GOP, pkt_size, and color metadata are all identical to
    # the working (unscaled) case. Sending the full source resolution
    # works reliably; HomeKit downscales on the client device.
    # TODO: investigate why any form of ffmpeg resolution scaling breaks
    #       HomeKit SRTP playback despite producing valid H.264.
    # -----------------------------------------------------------------
    if src_w > 0 and src_h > 0:
        result["target_resolution"] = (src_w, src_h)
    else:
        target_w = min(stream_width, max_width) if stream_width > 0 else max_width
        target_h = min(stream_height, max_height) if stream_height > 0 else max_height
        result["target_resolution"] = (target_w, target_h)

    # Minimum bitrate for the actual output resolution
    out_w, out_h = result["target_resolution"]
    if out_w > 0 and out_h > 0:
        target_pixels = out_w * out_h
        result["min_bitrate_kbps"] = max(300, target_pixels * 15 // 20000)
    else:
        result["min_bitrate_kbps"] = 300

    return result


##
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



class Camera(HomeAccessory,  PyhapCamera):
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
                #{"type": "AAC-eld","samplerate":16}
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

    #   super().__init__(driver, plugin, indigodeviceid, display_name, aid)  # *args, **kwargs)
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

        if "DoorBell_ID" in config:
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
            if self.plugin.debug7:
                _LOGGER.debug(
                    "[%s] Starting stream with the following parameters: %s",
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
                        "(e.g. H.265 sub-streams in Blue Iris are not supported over RTSP).\n"
                        "We always use Stream 2 in BlueIris Web Server Setup, adjust there.\n",
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
            # Enforce minimum bitrate for transcode  <-- HERE
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
            input_source = input_source + "&kbps=" + str(output_vars["v_max_bitrate"]) + "&cache=1"

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

    async def start_stream_old(self, session_info, stream_config):
        """Start a new stream with the given configuration."""
        try:
            if self.plugin.debug7:
                _LOGGER.debug(
                    "[%s] Starting stream -I'm Here 2- with the following parameters: %s",
                    session_info["id"],
                    stream_config
                )
            self.base_config = stream_config

            input_source = self.config.get(CONF_STREAM_SOURCE)

            # --- Log ffprobe results if available ---
            ffprobe_video = self.config.get("ffprobe_video")
            ffprobe_audio = self.config.get("ffprobe_audio")

            if ffprobe_video:
                _LOGGER.debug(
                    "[%s] ffprobe video: codec=%s %sx%s@%sfps pix_fmt=%s profile=%s copy_safe=%s action=%s",
                    self.display_name,
                    ffprobe_video.get("codec"),
                    ffprobe_video.get("width"),
                    ffprobe_video.get("height"),
                    ffprobe_video.get("fps"),
                    ffprobe_video.get("pix_fmt"),
                    ffprobe_video.get("profile"),
                    ffprobe_video.get("copy_safe"),
                    ffprobe_video.get("action"),
                )
                if ffprobe_video.get("copy_safe") and self.config[CONF_VIDEO_CODEC] != "copy":
                    _LOGGER.info(
                        "[%s] Stream is H.264+yuv420p — video_codec is '%s' but could use 'copy' to save CPU",
                        self.display_name, self.config[CONF_VIDEO_CODEC],
                    )
                elif ffprobe_video.get("codec") == "unknown":
                    _LOGGER.info(
                        "\n[%s] ffprobe could not identify the video codec in this stream. \n"
                        "This usually means the camera's RTSP sub-stream is not properly configured\n "
                        "(e.g. H.265 sub-streams in Blue Iris are not supported over RTSP).\n"
                        "We always use Stream 2 in BlueIris Web Server Setup, adjust there\n",
                                       self.display_name,
                    )
                elif not ffprobe_video.get("copy_safe") and self.config[CONF_VIDEO_CODEC] == "copy":
                    _LOGGER.debug(
                        "[%s] video_codec is 'copy' but ffprobe says copy is NOT safe (codec=%s pix_fmt=%s) — will transcode instead",
                        self.display_name,
                        ffprobe_video.get("codec"),
                        ffprobe_video.get("pix_fmt"),
                    )
            else:
                _LOGGER.debug("[%s] No ffprobe data available — run 'Check Camera Stream Compatibility' menu item",
                              self.display_name)


## ffprobe audio
            if self.config[CONF_SUPPORT_AUDIO] and ffprobe_audio:
                if ffprobe_audio.get("present") is False or (
                        not ffprobe_audio.get("codec") and not ffprobe_audio.get("sample_rate")):
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


            extra_commands = self.config.get("start_commands_extra", "")
            # HEVC transcode needs larger probe to find a keyframe

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
            audio_frame_duration = ""

            if self.config[CONF_AUDIO_CODEC] == "libopus":
                audio_application = "-application lowdelay "
                opus_frame_duration = stream_config.get('a_packet_time', 20)
                valid_opus_durations = [2.5, 5, 10, 20, 40, 60, 80, 100, 120]
                if opus_frame_duration not in valid_opus_durations:
                    _LOGGER.debug(
                        "[%s] Requested frame duration %s not valid for Opus, using 20",
                        self.display_name, opus_frame_duration,
                    )
                    opus_frame_duration = 20
                audio_frame_duration = f"-frame_duration {opus_frame_duration} "
            # Start audio proxy to convert Opus RTP timestamps from 48kHz
            # (FFmpeg's hardcoded Opus RTP clock rate per RFC 7587) to the
            # sample rate negotiated by HomeKit (typically 16kHz).
            # a_sample_rate is in kHz (e.g. 16 for 16000 Hz) from pyhap TLV.
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
                            "[%s] Audio proxy failed — local_port=%s, returncode=%s, "
                            "pid=%s (no stderr captured)",
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

            # stream_config["v_max_bitrate"] = self.config["v_max_bitrate"]
            output_vars = stream_config.copy()
            output_vars.update(
                {
                    "v_profile": video_profile,
                #    "v_max_bitrate" : stream_config["v_max_bitrate"] *4,
                    "v_bufsize": stream_config["v_max_bitrate"] * 4,
                    "v_map": self.config[CONF_VIDEO_MAP],
                    "fps": self.config[CONF_MAX_FPS],
                    "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                    "v_codec": self.config[CONF_VIDEO_CODEC],
                    "a_bufsize": stream_config["a_max_bitrate"] * 4,
                    "a_map": self.config[CONF_AUDIO_MAP],
                    "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                    "a_encoder": self.config[CONF_AUDIO_CODEC],
                    "a_application": audio_application,
                    "a_frame_duration": audio_frame_duration,
                    "a_proxy_port": audio_proxy.local_port if audio_proxy else 0,
                }
            )

            # Select video output: transcode only if ffprobe says copy is NOT safe
            if ffprobe_video and ffprobe_video.get("copy_safe") is False:
                _LOGGER.info("[%s] ffprobe: source not copy-safe (codec=%s pix_fmt=%s) — transcoding with libx264",
                             self.display_name, ffprobe_video.get("codec"), ffprobe_video.get("pix_fmt"))
                output = VIDEO_OUTPUT_TRANSCODE.format(**output_vars)
            else:
                # Default: copy passthrough (existing behaviour, also used when no ffprobe data)
                output = VIDEO_OUTPUT.format(**output_vars)

            if self.config[CONF_SUPPORT_AUDIO]:
                output = output + " " + AUDIO_OUTPUT.format(**output_vars)

            _LOGGER.debug(f"FFmpeg output_vars {output_vars}")
            _LOGGER.debug("FFmpeg output settings: %s", output)

            # --- Summary: config vs probe ---
            if ffprobe_video:
                _LOGGER.debug(
                    "[%s] Stream summary: source=%sx%s@%sfps(%s) → config video_codec=%s, audio_codec=%s, support_audio=%s",
                    self.display_name,
                    ffprobe_video.get("width"),
                    ffprobe_video.get("height"),
                    ffprobe_video.get("fps"),
                    ffprobe_video.get("codec"),
                    self.config[CONF_VIDEO_CODEC],
                    self.config[CONF_AUDIO_CODEC],
                    self.config[CONF_SUPPORT_AUDIO],
                )

            _LOGGER.debug(
               '[%s] Starting stream with the following parameters: %s',
               session_info['id'],
               stream_config
            )

            ## if Blueiris modify.  No checks for that as yet.
            input_source =  input_source + "&kbps="+str(output_vars["v_max_bitrate"])+"&cache=1" #' ##&h="+str(stream_config["height"])+"&fps="+str(output_vars["fps"])

            # HEVC transcode needs larger probe to find a keyframe
            if ffprobe_video and ffprobe_video.get("codec") == "hevc":
                input_source = "-probesize 5000000 -analyzeduration 3000000 -rtsp_transport tcp -i " + input_source
                _LOGGER.debug("[%s] HEVC source — larger probesize for transcode", self.display_name)
            else:
                input_source = "-rtsp_transport tcp -i " + input_source

            _LOGGER.debug(fr"\nINPUT SOURCE:\n{input_source=}")

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
                self.plugin.ffmpeg_lastCommand.insert(0,f"{str(self.plugin.ffmpeg_command_line)}" )
                self.plugin.ffmpeg_lastCommand.extend(input_source.split())
                self.plugin.ffmpeg_lastCommand.extend(output.split())
                self.plugin.ffmpeg_lastCommand.extend(extra_cmd_toadd.split())
            except:
                _LOGGER.debug(f"Error creating ffmpeg_lastCommand {self.plugin.ffmpeg_command_line=} {input_source=} {output=} {extra_cmd_toadd=}")
                pass

            session_info["stream"] = stream
            session_info[FFMPEG_PID] = stream.process.pid
            session_info[AUDIO_PROXY] = audio_proxy
            stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)

            async def watch_session():
                #_LOGGER.debug(f"Watch Session called")
                await self._async_ffmpeg_watch(session_info["id"])

            session_info[FFMPEG_LOGGER] = asyncio.create_task(
                self._async_log_stderr_stream(stderr_reader)
            )

            session_info[FFMPEG_WATCHER] = SimpleIntervalScheduler(
                watch_session,
                FFMPEG_WATCH_INTERVAL,
            )

            session_info[FFMPEG_WATCHER].start()
            _LOGGER.debug(f"Started Watcher for ffmpeg Stream.")

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
            #_LOGGER.debug("%s: ffmpeg: %s", self.display_name, line.rstrip())

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
            _LOGGER.debug('RECONFIG STREAM CALLED: Interesting may be options for managing later\nSession Info {}\n\nStream Config\n{}\n'.format(session_info,stream_config))
      #  _LOGGER.debug("Attempting to stop current stream and reconfigure as requested....")
        # ## Stop stream in this async call
        session_id = session_info["id"]
        return True

        ## Below was an attempt to reconfigure streams when requested.  First copies all stream info as reconfigure doesn't include most info
        ## Only seems to include what had changed eg. video bit-rate
        ## Below sucessfully stops ffmpeg instance, and creates a new one using the updated video info.  Unfortunately the client never receives the message and video freezes on client
        ## Maybe a missing call to client to force update...
        ## On reviewing - it seems no one implements reconfigure

        # if not (stream := session_info.get("stream")):
        #     _LOGGER.debug("No stream for session ID %s", session_id)
        #
        # self._async_stop_ffmpeg_watch(session_id)
        #
        # if not pid_is_alive(stream.process.pid):
        #     _LOGGER.info("[%s] Stream already stopped", session_id)
        #
        # for shutdown_method in ("close", "kill"):
        #     _LOGGER.info("[%s] %s video stream", session_id, shutdown_method)
        #     try:
        #         await getattr(stream, shutdown_method)()
        #     except Exception:  # pylint: disable=broad-except
        #         _LOGGER.debug(
        #             "[%s] Failed to %s stream", session_id, shutdown_method
        #         )
        #
        # _LOGGER.info(f"Reconfiguring Stream as requested, Stopping & Quickly restarting...")
        #
        # try:
        #     _LOGGER.debug(
        #         "[%s] Starting stream - In reconfigure - with the following parameters: %s",
        #         session_info["id"],
        #         stream_config
        #     )
        #
        #     for config_key, conf in self.base_config.items():
        #         if config_key not in stream_config:
        #             stream_config[config_key] = conf
        #
        #
        #     input_source = self.config.get(CONF_STREAM_SOURCE)
        #     extra_commands = self.config.get("start_commands_extra", None)
        #
        #     _LOGGER.debug("Input Source\n{}".format(input_source))
        #
        #     video_profile = ""
        #     if self.config[CONF_VIDEO_CODEC] != "copy":
        #         video_profile = (
        #                 "-profile:v "
        #                 + VIDEO_PROFILE_NAMES[
        #                     int.from_bytes(stream_config["v_profile_id"], byteorder="big")
        #                 ]
        #                 + " "
        #         )
        #
        #     audio_application = ""
        #     if self.config[CONF_AUDIO_CODEC] == "libopus":
        #         audio_application = "-application lowdelay "
        #
        #     output_vars = stream_config.copy()
        #     output_vars.update(
        #         {
        #             "v_profile": video_profile,
        #             "v_bufsize": stream_config["v_max_bitrate"] * 4,
        #             "v_map": self.config[CONF_VIDEO_MAP],
        #             "fps": self.config[CONF_MAX_FPS],
        #             "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
        #             "v_codec": self.config[CONF_VIDEO_CODEC],
        #             "a_bufsize": stream_config["a_max_bitrate"] * 4,
        #             "a_map": self.config[CONF_AUDIO_MAP],
        #             "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
        #             "a_encoder": self.config[CONF_AUDIO_CODEC],
        #             "a_application": audio_application,
        #         }
        #     )
        #     output = VIDEO_OUTPUT.format(**output_vars)
        #
        #     if self.config[CONF_SUPPORT_AUDIO]:
        #         output = output + " " + AUDIO_OUTPUT.format(**output_vars)
        #     _LOGGER.debug(f"FFmpeg output_vars {output_vars}")
        #     _LOGGER.debug("FFmpeg output settings: %s", output)
        #
        #     _LOGGER.debug(
        #         '[%s] Starting stream with the following parameters: %s',
        #         session_info['id'],
        #         stream_config
        #     )
        #
        #     input_source =  input_source + "&kbps="+str(output_vars["v_max_bitrate"]) #' ##&h="+str(stream_config["height"])+"&fps="+str(output_vars["fps"])
        #
        #     input_source = "-rtsp_transport tcp -i " + input_source
        #
        #     stream = IndigoFFmpeg("./ffmpeg/ffmpeg" + str(self.plugin.ffmpeg_command_line))
        #     opened = await stream.open(
        #         cmd=[],
        #         input_source=input_source,
        #         output=output,
        #         extra_cmd="-hide_banner -nostats",
        #         stderr_pipe=True,
        #         stdout_pipe=False,
        #     )
        #     if not opened:
        #         _LOGGER.error("Failed to open ffmpeg stream")
        #         return False
        #
        #     _LOGGER.info(
        #         "[%s] Started video stream process - PID %d",
        #         session_info["id"],
        #         stream.process.pid,
        #     )
        #
        #     session_info["stream"] = stream
        #     session_info[FFMPEG_PID] = stream.process.pid
        #
        #     stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)
        #
        #     async def watch_session(_: Any) -> None:
        #         await self._async_ffmpeg_watch(session_info["id"])
        #
        #     session_info[FFMPEG_LOGGER] = asyncio.create_task(
        #         self._async_log_stderr_stream(stderr_reader)
        #     )
        #
        #     return await self._async_ffmpeg_watch(session_info["id"])


     ##   except:
      #      _LOGGER.exception("Start Stream Exception")

       # return True

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
    #async def async_get_snapshot(self, image_size):
        try:
            debug_function = False
            if self.plugin.debug7:
                debug_function = True
            if "BI_name" in self.config:
                camname = self.config["BI_name"]
                #_LOGGER.info("Get_Snapshot Config: called for this camera Name {}".format(camname ))
                if "image-width" in image_size:
                    width = image_size["image-width"]
                else:
                    width = 1380
                self.plugin.camera_snapShot_Requested_que.put((camname,width))  # que a tuple..
                #_LOGGER.info("Image Size:{}".format(image_size))
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
            _LOGGER.debug("Error in get snapshot:",exc_info=True)
            raise


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
