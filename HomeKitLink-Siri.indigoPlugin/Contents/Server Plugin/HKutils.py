from typing import Any
import math
import colorsys
import socket
import ujson
import os

# Temperature units
TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"
TEMP_KELVIN = "K"
MAX_PORT = 65535

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
    """Convert a temperature in Celsius to Fahrenheit."""
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
    """Convert absolute mired shift to degrees kelvin."""
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
    raise RuntimeError("nreachable")