from typing import Any
import math
import colorsys
import socket
import os
import asyncio
from typing import Callable, Optional

from datetime import timedelta, datetime
import logging

# Temperature units
TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"
TEMP_KELVIN = "K"
MAX_PORT = 65535

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

HOMEKIT_CHAR_TRANSLATIONS = {
    0: " ",  # nul
    10: " ",  # nl
    13: " ",  # cr
    33: "-",  # !
    34: " ",  # "
    36: "-",  # $
    37: "-",  # %
    40: "-",  # (
    41: "-",  # )
    42: "-",  # *
    43: "-",  # +
    47: "-",  # /
    58: "-",  # :
    59: "-",  # ;
    60: "-",  # <
    61: "-",  # =
    62: "-",  # >
    63: "-",  # ?
    64: "-",  # @
    91: "-",  # [
    92: "-",  # \
    93: "-",  # ]
    94: "-",  # ^
    95: " ",  # _
    96: "-",  # `
    123: "-",  # {
    124: "-",  # |
    125: "-",  # }
    126: "-",  # ~
    127: "-",  # del
}

class SimpleIntervalScheduler:
    def __init__(self, action: Callable[[], asyncio.Task], interval: timedelta):
        self.action = action
        self.interval = interval
        self.task: Optional[asyncio.Task] = None
        self.is_running = False
        self.logger = logging.getLogger("Plugin.HomeKitSpawn")

    async def _interval_listener(self):
        """Handler for elapsed intervals. Runs the action repeatedly at specified intervals."""
        while self.is_running:
            await asyncio.sleep(0.5)
            try:
                next_run_time = datetime.utcnow() + self.interval
                # Run the action
                await self.action()
                # Calculate the sleep time to maintain the interval
                sleep_seconds = max(0, (next_run_time - datetime.utcnow()).total_seconds())
                # Sleep until the next run time
                await asyncio.sleep(sleep_seconds)
            except Exception as e:
                self.logger.debug(f"Error occurred in the scheduled action: {e}", exc_info=True)
            except asyncio.CancelledError:
                # The task was cancelled, exit the loop
                self.logger.debug("Interval listener has been cancelled.")
                return

    def start(self):
        """Begin the interval actions."""
        if self.is_running:
            self.logger.debug("Interval listener already running.")
            return
        self.is_running = True
        self.task = asyncio.create_task(self._interval_listener())
        self.logger.debug("Interval listener started.")

    async def stop(self):
        """Cease the interval actions."""
        if not self.is_running or self.task is None:
            self.logger.debug("Interval listener is not running.")
            return
        self.is_running = False
        self.task.cancel()
        try:
            await self.task  # Wait for the task to be cancelled.
        except asyncio.CancelledError:
            self.logger.debug("Interval listener has been stopped.")
        finally:
            self.task = None
            self.logger.debug("Interval listener cleanup completed.")

def convert_to_float(state: Any) -> float | None:
    """Return float of state, catch errors."""
    try:
        return float(state)
    except (ValueError, TypeError):
        return None

def coerce_int(state: str) -> int:
    """Return int."""
    try:
        return int(state)
    except (ValueError, TypeError):
        return 0

def temperature_to_homekit(temperature: float | int, unit: str) -> float:
    """Convert temperature to Celsius for HomeKit."""
    return round(convert(temperature, unit, TEMP_CELSIUS), 1)

def fahrenheit_to_celsius(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    if interval:
        return fahrenheit / 1.8
    return (fahrenheit - 32.0) / 1.8

def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    if interval:
        return kelvin
    return kelvin - 273.15

def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    if interval:
        return celsius * 1.8
    return celsius * 1.8 + 32.0

def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Kelvin."""
    if interval:
        return celsius
    return celsius + 273.15

def convert(
    temperature: float, from_unit: str, to_unit: str, interval: bool = False
) -> float:
    if from_unit == to_unit:
        return temperature

    if from_unit == TEMP_CELSIUS:
        if to_unit == TEMP_FAHRENHEIT:
            return celsius_to_fahrenheit(temperature, interval)
        # kelvin
        return celsius_to_kelvin(temperature, interval)

    if from_unit == TEMP_FAHRENHEIT:
        if to_unit == TEMP_CELSIUS:
            return fahrenheit_to_celsius(temperature, interval)
        # kelvin
        return celsius_to_kelvin(fahrenheit_to_celsius(temperature, interval), interval)

        # from_unit == kelvin
    if to_unit == TEMP_CELSIUS:
        return kelvin_to_celsius(temperature, interval)
        # fahrenheit
    return celsius_to_fahrenheit(kelvin_to_celsius(temperature, interval), interval)

def color_temperature_mired_to_kelvin(mired_temperature: float) -> int:
    """Convert absolute mired shift to degrees kelvin."""
    return math.floor(1000000 / mired_temperature)

def color_temperature_kelvin_to_mired(kelvin_temperature: float) -> int:
    """Convert degrees kelvin to mired."""
    return math.floor(1000000 /  kelvin_temperature)

def pid_is_alive(pid: int) -> bool:
    """Check to see if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        pass
    return False

def density_to_air_quality(density: float) -> int:
    """Map PM2.5 density to HomeKit AirQuality level."""
    if density <= 35:
        return 1
    if density <= 75:
        return 2
    if density <= 115:
        return 3
    if density <= 150:
        return 4
    return 5

def density_to_air_quality_pm10(density: float) -> int:
    """Map PM10 density to HomeKit AirQuality level."""
    if density <= 40:
        return 1
    if density <= 80:
        return 2
    if density <= 120:
        return 3
    if density <= 300:
        return 4
    return 5

def density_to_air_quality_pm25(density: float) -> int:
    """Map PM2.5 density to HomeKit AirQuality level."""
    if density <= 25:
        return 1
    if density <= 50:
        return 2
    if density <= 100:
        return 3
    if density <= 300:
        return 4
    return 5

def color_temperature_to_hs(color_temperature_kelvin: float) -> tuple[float, float]:
    """Return an hs color from a color temperature in Kelvin."""
    return color_RGB_to_hs(*color_temperature_to_rgb(color_temperature_kelvin))

def color_RGB_to_hs(iR: float, iG: float, iB: float) -> tuple[float, float]:
    """Convert an rgb color to its hs representation."""
    return color_RGB_to_hsv(iR, iG, iB)[:2]

def color_RGB_to_hsv(iR: float, iG: float, iB: float) -> tuple[float, float, float]:
    """Convert an rgb color to its hsv representation.
    Hue is scaled 0-360
    Sat is scaled 0-100
    Val is scaled 0-100
    """
    fHSV = colorsys.rgb_to_hsv(iR / 255.0, iG / 255.0, iB / 255.0)
    return round(fHSV[0] * 360, 3), round(fHSV[1] * 100, 3), round(fHSV[2] * 100, 3)

def color_hsv_to_RGB(iH: float, iS: float, iV: float) -> tuple[int, int, int]:
    """Convert an hsv color into its rgb representation.
    Hue is scaled 0-360
    Sat is scaled 0-100
    Val is scaled 0-100
    """
    fRGB = colorsys.hsv_to_rgb(iH / 360, iS / 100, iV / 100)
    return (int(fRGB[0] * 255), int(fRGB[1] * 255), int(fRGB[2] * 255))

def color_temperature_to_rgb(
    color_temperature_kelvin: float,
) -> tuple[float, float, float]:
    """
    Return an RGB color from a color temperature in Kelvin.
    This is a rough approximation based on the formula provided by T. Helland
    http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
    """
    # range check
    if color_temperature_kelvin < 1000:
        color_temperature_kelvin = 1000
    elif color_temperature_kelvin > 40000:
        color_temperature_kelvin = 40000

    tmp_internal = color_temperature_kelvin / 100.0

    red = _get_red(tmp_internal)

    green = _get_green(tmp_internal)

    blue = _get_blue(tmp_internal)

    return red, green, blue

def _get_red(temperature: float) -> float:
    """Get the red component of the temperature in RGB space."""
    if temperature <= 66:
        return 255
    tmp_red = 329.698727446 * math.pow(temperature - 60, -0.1332047592)
    return _clamp(tmp_red)


def _get_green(temperature: float) -> float:
    """Get the green component of the given color temp in RGB space."""
    if temperature <= 66:
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
    else:
        green = 288.1221695283 * math.pow(temperature - 60, -0.0755148492)
    return _clamp(green)


def _get_blue(temperature: float) -> float:
    """Get the blue component of the given color temperature in RGB space."""
    if temperature >= 66:
        return 255
    if temperature <= 19:
        return 0
    blue = 138.5177312231 * math.log(temperature - 10) - 305.0447927307
    return _clamp(blue)

def _clamp(color_component: float, minimum: float = 0, maximum: float = 255) -> float:
    """
    Clamp the given color component value between the given min and max values.
    The range defined by the minimum and maximum values is inclusive, i.e. given a
    color_component of 0 and a minimum of 10, the returned value is 10.
    """
    color_component_out = max(color_component, minimum)
    return min(color_component_out, maximum)

def cleanup_name_for_homekit(name: str | None) -> str:
    """Ensure the name of the device will not crash homekit."""
    #
    # This is not a security measure.
    #
    # UNICODE_EMOJI is also not allowed but that
    # likely isn't a problem
    if name is None:
        return "None"  # None crashes apple watches
    return name.translate(HOMEKIT_CHAR_TRANSLATIONS)[:64]

def _get_test_socket() -> socket.socket:
    """Create a socket to test binding ports."""
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setblocking(False)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    return test_socket

def _port_is_available(port: int) -> bool:
    """Check to see if a port is available."""
    try:
        _get_test_socket().bind(("", port))
    except OSError:
        return False
    return True

def _find_next_available_port(start_port: int, exclude_ports: set) -> int:
    """Find the next available port starting with the given port."""
    test_socket = _get_test_socket()
    for port in range(start_port, MAX_PORT + 1):
        if port in exclude_ports:
            continue
        try:
            test_socket.bind(("", port))
            return port
        except OSError:
            if port == MAX_PORT:
                raise
            continue
    raise RuntimeError("Unreachable")

## ---------------------------------------------------------------------------------------------------------------
## Improved live view (plugin setting "liveImproved", on by default; off = live view as before 0.8.44). What other
## HomeKit projects do (Home Assistant, homebridge-unifi-protect, Scrypted, homebridge-camera-ffmpeg), mainly for
## Apple TV and hub-relayed (remote) viewing. Three parts, all on together:
##   ports  - send video from the port we tell HomeKit we send from (pyhap echoes the viewer's port back in
##            SetupEndpoints), so its RTCP reports reach us. Home Assistant: &localrtpport=<port>. Copy and re-encode.
##   encode - re-encoded streams only: one slice per frame (zerolatency's sliced threads split each frame), a keyframe
##            every 4 s instead of 0.5 s, 2x buffer, the level and frame rate HomeKit asked for. All streams: 1200-byte
##            packets (fits relayed and IPv6 paths).
##   scale  - re-encoded streams only: scale down to the size HomeKit asked for, never up, keeping the shape.
## (live_tuning can also limit them to listed viewer IPs; the setting applies them to every viewer.)
## Copied (passthrough) streams keep the camera's picture; only ports and packet size apply to them.
## ---------------------------------------------------------------------------------------------------------------
LIVE_TUNING_LEVELS = {0: "3.1", 1: "3.2", 2: "4.0"}

def live_tuning(plugin, address):
    """The live view tuning that applies to a viewer at address: a set of 'ports', 'encode', 'scale' (may be empty)."""
    on = {name for name, attr in (("ports", "liveTuningPorts"), ("encode", "liveTuningEncode"), ("scale", "liveTuningScale"))
          if getattr(plugin, attr, False)}
    if on and getattr(plugin, "liveTuningScope", "listed") == "listed" and str(address) not in getattr(plugin, "liveTuningViewers", set()):
        return set()
    return on

def _udp_ports_free(*ports):
    socks = []
    try:
        for port in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socks.append(s)
            s.bind(("", port))
        return True
    except OSError:
        return False
    finally:
        for s in socks:
            s.close()

def presumed_upgrade(plugin, stream_config):
    """Improved live view: start a mid-size request (640-1279 wide, e.g. 640x360 @ 132k for a remote view) at
    1280x720 and at least 299k. HomeKit nearly always asks for that a few seconds later (a reconfigure), which
    HKLS can't follow on a running stream, so the view used to stay at the low size. Smaller requests (Apple Watch)
    and larger ones are unchanged. Changes stream_config; returns a note for the log, or None."""
    if not getattr(plugin, "liveTuningEncode", False):
        return None
    width = int(stream_config.get("width", 0) or 0)
    height = int(stream_config.get("height", 0) or 0)
    bitrate = int(stream_config.get("v_max_bitrate", 0) or 0)
    if not 640 <= width < 1280:
        return None
    stream_config["width"], stream_config["height"] = 1280, 720
    stream_config["v_max_bitrate"] = max(bitrate, 299)
    stream_config["presumed_upgrade"] = True   ## still a remote / low-bandwidth view: use the camera's remote stream
    return f"started at 1280x720 @ {stream_config['v_max_bitrate']}k (HomeKit asked {width}x{height} @ {bitrate}k and usually raises it to this)"

def tune_live_video(video_output, tuning, stream_config, copy):
    """Apply the live view tuning to the formatted video part of an ffmpeg command. Returns (command, notes)."""
    import re
    notes = []
    out = video_output
    v_port = int(stream_config.get("v_port", 0) or 0)
    if "ports" in tuning and v_port:
        ## ffmpeg sends RTP from v_port and RTCP from v_port + 1 (unless localrtcpport is given)
        if _udp_ports_free(v_port, v_port + 1):
            out = re.sub(r"(srtp://\S+?\?\S*?)(pkt_size=)", r"\g<1>localrtpport={}&\g<2>".format(v_port), out, count=1)
            notes.append(f"ports: sending from {v_port}")
        else:
            notes.append(f"ports: {v_port} in use here, sending from a random port as before")
    if "encode" in tuning:
        out = re.sub(r"pkt_size=\d+", "pkt_size=1200", out, count=1)
        notes.append("1200-byte packets")
        if not copy:
            fps = int(stream_config.get("fps", 0) or 0) or 30
            gop = fps * 4
            out = out.replace("-tune zerolatency ", "-tune zerolatency -x264-params sliced-threads=0:slices=1 ", 1)
            out = re.sub(r"-g \d+ -keyint_min \d+ ", f"-g {gop} -keyint_min {gop} ", out, count=1)
            out = re.sub(r"-r \d+(\.\d+)? ", f"-r {fps} ", out, count=1)
            bitrate = int(stream_config.get("v_max_bitrate", 0) or 0)
            if bitrate:
                out = re.sub(r"-bufsize \d+k ", f"-bufsize {bitrate * 2}k ", out, count=1)
            level_raw = stream_config.get("v_level")
            level = LIVE_TUNING_LEVELS.get(int.from_bytes(level_raw, "big") if isinstance(level_raw, (bytes, bytearray)) else level_raw)
            if level:
                out = out.replace("-bf 0 ", f"-bf 0 -level:v {level} ", 1)
            notes.append(f"single slice, keyframe every 4 s (-g {gop}), 2x buffer, {fps} fps" + (f", level {level}" if level else ""))
    if "scale" in tuning and not copy:
        width, height = int(stream_config.get("width", 0) or 0), int(stream_config.get("height", 0) or 0)
        if width and height:
            scale = (f"-vf scale=w='min(iw\\,{width})':h='min(ih\\,{height})':force_original_aspect_ratio=decrease:force_divisible_by=2 ")
            out = out.replace("-pix_fmt yuv420p ", scale + "-pix_fmt yuv420p ", 1)
            notes.append(f"scaled to fit {width}x{height}")
    return out, notes

class RepeatedViews:
    """Quieter logging for repeated short live views of one camera, e.g. a Home widget that refreshes its
    picture by opening a stream for a second or two, over and over. The first view from a device at a size
    is logged as usual; when the same device asks for the same size again within WINDOW seconds and its last
    view lasted under SHORT seconds, that stream's lines go to debug (one INFO line says so). Normal logging
    resumes once the device has been quiet for WINDOW seconds. Real viewing (longer views) is always logged."""
    WINDOW = 600
    SHORT = 5.0

    def __init__(self):
        self._last_start = {}      # key -> monotonic time of the last view's start
        self._last_length = {}     # key -> length of the last finished view (seconds)
        self._sessions = {}        # session id -> (key, start, quiet)
        self._announced = set()

    def start(self, logger, name, address, width, height, session_id):
        """Log level for this session's lines (logging.INFO or logging.DEBUG)."""
        import time as _time
        key = (str(address), width, height)
        now = _time.monotonic()
        last = self._last_start.get(key)
        quiet = (last is not None and now - last < self.WINDOW and self._last_length.get(key, 999) < self.SHORT)
        self._last_start[key] = now
        if quiet and key not in self._announced:
            self._announced.add(key)
            logger.info("[%s] Repeated short live views from %s at %sx%s (for example a Home widget refreshing its "
                        "picture): logged at debug level until they stop for %d minutes",
                        name, address, width, height, self.WINDOW // 60)
        elif not quiet:
            self._announced.discard(key)
        self._sessions[str(session_id)] = (key, now, quiet)
        return logging.DEBUG if quiet else logging.INFO

    def stop(self, session_id):
        """Log level for this session's closing line; records how long it lasted."""
        import time as _time
        key, start, quiet = self._sessions.pop(str(session_id), (None, None, False))
        if key is not None:
            length = _time.monotonic() - start
            self._last_length[key] = length
            if length >= self.SHORT:
                return logging.INFO   ## a real view: its end is always logged, even if its start went to debug
        return logging.DEBUG if quiet else logging.INFO
