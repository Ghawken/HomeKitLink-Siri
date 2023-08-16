import asyncio
import base64
import functools
import ujson
import random
import socket
from uuid import UUID

from .const import BASE_UUID

import logging
logger = logging.getLogger("Plugin.HomeKit_pyHap")

ALPHANUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
HEX_DIGITS = "0123456789ABCDEF"

rand = random.SystemRandom()


def callback(func):
    """Decorator for non blocking functions."""
    setattr(func, "_pyhap_callback", True)
    return func


def is_callback(func):
    """Check if function is callback."""
    return "_pyhap_callback" in getattr(func, "__dict__", {})


def iscoro(func):
    """Check if the function is a coroutine or if the function is a ``functools.partial``,
    check the wrapped function for the same.
    """
    if isinstance(func, functools.partial):
        func = func.func
    return asyncio.iscoroutinefunction(func)


def get_local_address():
    """
    Grabs the local IP address using a socket.

    :return: Local IP Address in IPv4 format.
    :rtype: str
    """
    # TODO: try not to talk 8888 for this
    addr = ""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        #s.connect(("8.8.8.8", 80))
        #addr = s.getsockname()[0]
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.connect(('10.255.255.255', 80))
        addr = s.getsockname()[0]
        logger.debug(f"Using IP Address for Homekit Server : {addr}.  To manually change see advanced options in Plugin config")
    except:
        logger.error(f"Error Getting local address IP address.  See debug log for more details.")
        logger.error(f"This is a breaking issue which until fixed will cause no connection to be possible.")
        logger.debug(f"Exception trying to get local IP address", exc_info=True)
        logger.error(f"Try setting Interface for HAP in advanced options, Home Server Options:Interface setting")
    finally:
        s.close()
    return str(addr)


def long_to_bytes(n):
    """
    Convert a ``long int`` to ``bytes``

    :param n: Long Integer
    :type n: int

    :return: ``long int`` in ``bytes`` format.
    :rtype: bytes
    """
    byteList = []
    x = 0
    off = 0
    while x != n:
        b = (n >> off) & 0xFF
        byteList.append(b)
        x = x | (b << off)
        off += 8
    byteList.reverse()
    return bytes(byteList)


def generate_mac():
    """
    Generates a fake mac address used in broadcast.

    :return: MAC address in format XX:XX:XX:XX:XX:XX
    :rtype: str
    """
    return "{}{}:{}{}:{}{}:{}{}:{}{}:{}{}".format(  # pylint: disable=consider-using-f-string
        *(rand.choice(HEX_DIGITS) for _ in range(12))
    )


def generate_setup_id():
    """
    Generates a random Setup ID for an ``Accessory`` or ``Bridge``.

    Used in QR codes and the setup hash.

    :return: 4 digit alphanumeric code.
    :rtype: str
    """
    return "".join([rand.choice(ALPHANUM) for i in range(4)])


def generate_pincode():
    """
    Generates a random pincode.

    :return: pincode in format ``xxx-xx-xxx``
    :rtype: bytearray
    """
    return "{}{}{}-{}{}-{}{}{}".format(  # pylint: disable=consider-using-f-string
        *(rand.randint(0, 9) for i in range(8))
    ).encode("ascii")


def to_base64_str(bytes_input) -> str:
    return base64.b64encode(bytes_input).decode("utf-8")


def base64_to_bytes(str_input) -> bytes:
    return base64.b64decode(str_input.encode("utf-8"))


def byte_bool(boolv):
    return b"\x01" if boolv else b"\x00"


async def event_wait(event, timeout):
    """Wait for the given event to be set or for the timeout to expire.

    :param event: The event to wait for.
    :type event: asyncio.Event

    :param timeout: The timeout for which to wait, in seconds.
    :type timeout: float

    :return: ``event.is_set()``
    :rtype: bool
    """
    try:
        await asyncio.wait_for(event.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    return event.is_set()

@functools.lru_cache(maxsize=2048)
def uuid_to_hap_type(uuid):
    """Convert a UUID to a HAP type."""
    long_type = str(uuid).upper()
    if not long_type.endswith(BASE_UUID):
        return long_type
    return long_type.split("-", 1)[0].lstrip("0")

@functools.lru_cache(maxsize=2048)
def hap_type_to_uuid(hap_type):
    """Convert a HAP type to a UUID."""
    if "-" in hap_type:
        return UUID(hap_type)
    return UUID("0" * (8 - len(hap_type)) + hap_type + BASE_UUID)

## Use ujson x4 times as fast, not as good as orjson, but is installed by default in Indigo 2022.2 as Sanic/Webserver needs
## Issue is orjson dumps = bytes output, json and ujson = string output hence need for encoding here.
def to_hap_json(dump_obj):
    """Convert an object to HAP json."""
    return ujson.dumps(dump_obj, separators=(",", ":")).encode("utf-8")  # pylint: disable=no-member

def to_sorted_hap_json(dump_obj):
    """Convert an object to sorted HAP json."""
    return ujson.dumps(dump_obj, sort_keys=True,separators=(",", ":")).encode("utf-8")

def from_hap_json(json_str):
    """Convert json to an object."""
    return ujson.loads(json_str)  # pylint: disable=no-member
