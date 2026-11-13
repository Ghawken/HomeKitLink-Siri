"""HomeKit Data Stream (HDS) for HomeKit Secure Video.

Only used when an HKSV Recorder device exists for a camera.

Ported from HAP-NodeJS lib/datastream (DataStreamServer.js, DataStreamParser.js):

  * Setup: the hub writes SetupDataStreamTransport with a 32-byte controller
    salt. We pick a 32-byte accessory salt and derive two ChaCha20-Poly1305
    keys with HKDF-SHA512(salt = controller_salt + accessory_salt,
    ikm = HAP session shared secret, info = "HDS-Read-Encryption-Key" /
    "HDS-Write-Encryption-Key"), then tell the hub which TCP port to connect to.
  * Frames: 1 byte type (1) + 3 byte big-endian length, then the encrypted
    payload and a 16-byte tag. The 4-byte frame header is the AAD; the nonce is
    a 64-bit little-endian counter per direction (padded to 12 bytes).
  * Payload: 1 byte header length, header dict, message dict - both in Apple's
    compact binary encoding (below).
  * First message must be control/hello; we answer it. dataSend (the actual
    recording transfer) is handled by hksv_recorder.py.

Changes from PR #42's version: the listener binds only to the local address
the hub's HAP connection uses, accepts connections only from that hub while a
session is prepared, checks the first frame's size before reading it, limits
connections, and waits for the socket to drain when sending.
"""

import asyncio
import logging
import os
import socket
import struct
import time
import uuid as uuidlib
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn.HKSV")
DEBUG = False   # set by HKSV.set_debug


def _dbg(msg, *args, **kwargs):
    if DEBUG:
        _LOGGER.info("HKSV debug: " + msg, *args, **kwargs)
    else:
        _LOGGER.debug(msg, *args, **kwargs)


READ_INFO = b"HDS-Read-Encryption-Key"     # accessory -> controller
WRITE_INFO = b"HDS-Write-Encryption-Key"   # controller -> accessory
MAX_PAYLOAD = 0xFFFFF
PREPARED_TIMEOUT = 10.0
HELLO_TIMEOUT = 10.0
MAX_CONNECTIONS = 8          # each home hub keeps one; a home rarely has more than a few


# --------------------------------------------------------------------- codec
class Int64(int):
    """Force the INT64LE encoding (HAP-NodeJS always sends id/status this way)."""


class Terminator:
    pass


_TERMINATOR = Terminator()
_EPOCH_2001 = datetime(2001, 1, 1, tzinfo=timezone.utc).timestamp()


def encode(value):
    out = bytearray()
    _encode(value, out)
    return bytes(out)


def _encode_len(out, start, l8, l16, l32, l64, short_max, payload):
    n = len(payload)
    if n <= short_max:
        out.append(start + n)
    elif n <= 0xFF:
        out.append(l8)
        out.append(n)
    elif n <= 0xFFFF:
        out.append(l16)
        out += struct.pack("<H", n)
    elif n <= 0xFFFFFFFF:
        out.append(l32)
        out += struct.pack("<I", n)
    else:
        out.append(l64)
        out += struct.pack("<Q", n)
    out += payload


def _encode(v, out):
    if v is None:
        out.append(0x04)
    elif v is True:
        out.append(0x01)
    elif v is False:
        out.append(0x02)
    elif isinstance(v, Int64):
        out.append(0x33)
        out += struct.pack("<q", int(v))
    elif isinstance(v, int):
        if v == -1:
            out.append(0x07)
        elif 0 <= v <= 38:
            out.append(0x08 + v)
        elif -0x80 <= v <= 0x7F:
            out.append(0x30)
            out += struct.pack("<b", v)
        elif -0x8000 <= v <= 0x7FFF:
            out.append(0x31)
            out += struct.pack("<h", v)
        elif -0x80000000 <= v <= 0x7FFFFFFF:
            out.append(0x32)
            out += struct.pack("<i", v)
        else:
            out.append(0x33)
            out += struct.pack("<q", v)
    elif isinstance(v, float):
        out.append(0x36)
        out += struct.pack("<d", v)
    elif isinstance(v, str):
        _encode_len(out, 0x40, 0x61, 0x62, 0x63, 0x64, 32, v.encode("utf-8"))
    elif isinstance(v, (bytes, bytearray, memoryview)):
        _encode_len(out, 0x70, 0x91, 0x92, 0x93, 0x94, 32, bytes(v))
    elif isinstance(v, uuidlib.UUID):
        out.append(0x05)
        out += v.bytes
    elif isinstance(v, (list, tuple)):
        if len(v) <= 14:
            out.append(0xD0 + len(v))
            for item in v:
                _encode(item, out)
        else:
            out.append(0xDF)
            for item in v:
                _encode(item, out)
            out.append(0x03)
    elif isinstance(v, dict):
        items = list(v.items())
        if len(items) <= 14:
            out.append(0xE0 + len(items))
            for k, val in items:
                _encode(k, out)
                _encode(val, out)
        else:
            out.append(0xEF)
            for k, val in items:
                _encode(k, out)
                _encode(val, out)
            out.append(0x03)
    else:
        raise TypeError("HDS encode: unsupported type {}".format(type(v)))


class _Reader:
    def __init__(self, data):
        self.d = bytes(data)
        self.i = 0
        self.tracked = []

    def take(self, n):
        if self.i + n > len(self.d):
            raise ValueError("HDS decode: out of data")
        b = self.d[self.i:self.i + n]
        self.i += n
        return b

    def track(self, v):
        self.tracked.append(v)
        return v


def decode(data):
    r = _Reader(data)
    return _decode(r)


def _decode(r):
    tag = r.take(1)[0]
    if tag == 0x00:
        raise ValueError("HDS decode: zero tag")
    if tag == 0x01:
        return r.track(True)
    if tag == 0x02:
        return r.track(False)
    if tag == 0x03:
        return _TERMINATOR
    if tag == 0x04:
        return None
    if tag == 0x05:
        return r.track(uuidlib.UUID(bytes=r.take(16)))
    if tag == 0x06:
        secs = struct.unpack("<d", r.take(8))[0]
        return r.track(datetime.fromtimestamp(_EPOCH_2001 + secs, tz=timezone.utc))
    if tag == 0x07:
        return r.track(-1)
    if 0x08 <= tag <= 0x2F:      # small integers 0-39
        return r.track(tag - 0x08)
    if tag == 0x30:
        return r.track(struct.unpack("<b", r.take(1))[0])
    if tag == 0x31:
        return r.track(struct.unpack("<h", r.take(2))[0])
    if tag == 0x32:
        return r.track(struct.unpack("<i", r.take(4))[0])
    if tag == 0x33:
        return r.track(struct.unpack("<q", r.take(8))[0])
    if tag == 0x35:
        return r.track(struct.unpack("<f", r.take(4))[0])
    if tag == 0x36:
        return r.track(struct.unpack("<d", r.take(8))[0])
    if 0x40 <= tag <= 0x60:
        return r.track(r.take(tag - 0x40).decode("utf-8"))
    if tag in (0x61, 0x62, 0x63, 0x64):
        n = struct.unpack({0x61: "<B", 0x62: "<H", 0x63: "<I", 0x64: "<Q"}[tag],
                          r.take({0x61: 1, 0x62: 2, 0x63: 4, 0x64: 8}[tag]))[0]
        return r.track(r.take(n).decode("utf-8"))
    if tag == 0x6F:
        end = r.d.index(b"\x00", r.i)
        s = r.d[r.i:end].decode("utf-8")
        r.i = end + 1
        return r.track(s)
    if 0x70 <= tag <= 0x90:
        return r.track(r.take(tag - 0x70))
    if tag in (0x91, 0x92, 0x93, 0x94):
        n = struct.unpack({0x91: "<B", 0x92: "<H", 0x93: "<I", 0x94: "<Q"}[tag],
                          r.take({0x91: 1, 0x92: 2, 0x93: 4, 0x94: 8}[tag]))[0]
        return r.track(r.take(n))
    if tag == 0x9F:
        end = r.d.index(b"\x03", r.i)
        b = r.d[r.i:end]
        r.i = end + 1
        return r.track(b)
    if 0xA0 <= tag <= 0xCF:
        idx = tag - 0xA0
        if idx >= len(r.tracked):
            raise ValueError("HDS decode: bad compression index {}".format(idx))
        return r.tracked[idx]
    if 0xD0 <= tag <= 0xDE:
        return [_decode(r) for _ in range(tag - 0xD0)]
    if tag == 0xDF:
        arr = []
        while True:
            v = _decode(r)
            if v is _TERMINATOR:
                return arr
            arr.append(v)
    if 0xE0 <= tag <= 0xEE:
        d = {}
        for _ in range(tag - 0xE0):
            k = _decode(r)
            d[k] = _decode(r)
        return d
    if tag == 0xEF:
        d = {}
        while True:
            k = _decode(r)
            if k is _TERMINATOR:
                return d
            d[k] = _decode(r)
    raise ValueError("HDS decode: unknown tag 0x{:02x}".format(tag))


# -------------------------------------------------------------------- crypto
def derive_keys(shared_secret, controller_salt, accessory_salt):
    salt = controller_salt + accessory_salt

    def hkdf(info):
        return HKDF(algorithm=hashes.SHA512(), length=32, salt=salt, info=info).derive(shared_secret)
    return hkdf(READ_INFO), hkdf(WRITE_INFO)


def _nonce(counter):
    return b"\x00\x00\x00\x00" + struct.pack("<Q", counter)


# -------------------------------------------------------------------- server
class _Prepared:
    def __init__(self, a2c_key, c2a_key, label):
        self.a2c = ChaCha20Poly1305(a2c_key)
        self.c2a = ChaCha20Poly1305(c2a_key)
        self.label = label
        self.created = time.monotonic()


class HDSConnection:
    def __init__(self, server, reader, writer, prepared):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.p = prepared
        self.a2c_nonce = 0
        self.c2a_nonce = 0
        self.ready = False
        self.peer = writer.get_extra_info("peername")
        self.handlers = {}   # (protocol, topic) -> callable(conn, id, message)

    def send(self, header, message):
        payload = bytearray()
        hdr = encode(header)
        payload.append(len(hdr))
        payload += hdr
        payload += encode(message)
        frame_header = b"\x01" + struct.pack(">I", len(payload))[1:]
        ct = self.p.a2c.encrypt(_nonce(self.a2c_nonce), bytes(payload), frame_header)
        self.a2c_nonce += 1
        self.writer.write(frame_header + ct)

    async def drain(self):
        """Wait until the hub has taken what was sent (stops memory growing on a slow hub)."""
        await self.writer.drain()

    def send_response(self, protocol, topic, msg_id, status=0, message=None):
        self.send({"protocol": protocol, "response": topic, "id": Int64(msg_id), "status": Int64(status)},
                  message or {})

    def send_event(self, protocol, topic, message):
        self.send({"protocol": protocol, "event": topic}, message)

    def send_request(self, protocol, topic, msg_id, message):
        self.send({"protocol": protocol, "request": topic, "id": Int64(msg_id)}, message)

    async def read_frame(self):
        head = await self.reader.readexactly(4)
        length = int.from_bytes(head[1:4], "big")
        if length > MAX_PAYLOAD:
            raise ValueError("HDS frame too large")
        body = await self.reader.readexactly(length + 16)
        if head[0] != 1:
            return None
        plain = self.p.c2a.decrypt(_nonce(self.c2a_nonce), body, head)
        self.c2a_nonce += 1
        hlen = plain[0]
        header = decode(plain[1:1 + hlen])
        message = decode(plain[1 + hlen:]) if len(plain) > 1 + hlen else {}
        return header, message

    async def run(self):
        name = self.server.name
        try:
            while True:
                timeout = None if self.ready else HELLO_TIMEOUT
                got = await asyncio.wait_for(self.read_frame(), timeout)
                if got is None:
                    continue
                header, message = got
                protocol = header.get("protocol")
                if "request" in header:
                    topic, mid = header["request"], header.get("id", 0)
                    if not self.ready:
                        if (protocol, topic) != ("control", "hello"):
                            _LOGGER.warning("[%s] HDS: first message wasn't hello (%s/%s) - closing", name, protocol, topic)
                            return
                        self.ready = True
                        self.server.log_once("hello-{}".format(self.peer[0] if self.peer else "?"),
                                             "[{}] HDS: hub {} connected - data stream ready".format(
                                                 name, self.peer[0] if self.peer else "?"))
                        self.send_response("control", "hello", mid)
                        await self.drain()
                        continue
                    self.server.last_contact()
                    handler = self.server.request_handlers.get((protocol, topic))
                    if handler:
                        handler(self, mid, message)
                    else:
                        self.server.log_once("unhandled-{}-{}".format(protocol, topic),
                                             "[{}] HKSV: hub asked for {}/{} - not supported".format(name, protocol, topic))
                        _dbg("[%s] HDS: request %s/%s %s", name, protocol, topic, _summarise(message))
                        # 6 = protocol specific error, as HAP-NodeJS uses for unsupported
                        self.send_response(protocol, topic, mid, status=6)
                    await self.drain()
                elif "event" in header:
                    self.server.last_contact()
                    handler = self.server.event_handlers.get((protocol, header["event"]))
                    if handler:
                        handler(self, message)
                    else:
                        _dbg("[%s] HDS: event %s/%s %s", name, protocol, header["event"], _summarise(message))
                elif "response" in header:
                    _dbg("[%s] HDS: response %s/%s status %s", name, protocol, header["response"],
                                  header.get("status"))
        except asyncio.TimeoutError:
            _LOGGER.warning("[%s] HDS: hub connected but didn't say hello in time", name)
        except asyncio.IncompleteReadError:
            _dbg("[%s] HDS: hub closed the data stream", name)
        except Exception:
            _LOGGER.warning("[%s] HDS: data stream error", name, exc_info=True)
        finally:
            try:
                self.writer.close()
            except Exception:
                pass
            self.server.connection_closed(self)


def _summarise(message):
    try:
        return {k: (("<{} bytes>".format(len(v))) if isinstance(v, (bytes, bytearray)) else v)
                for k, v in (message or {}).items()}
    except Exception:
        return "?"


class HDSServer:
    """HomeKit Data Stream listener for one camera accessory.

    A listener is opened on demand, bound to the local address the hub's HAP
    connection arrived on (so interface/IPv6 settings are respected), and only
    connections from a hub with a prepared session are read.
    """

    def __init__(self, name, loop, on_change=None):
        self.name = name
        self.loop = loop
        self.listeners = {}          # local address -> [asyncio server, port, socket]
        self.prepared = []
        self.connections = []
        self.request_handlers = {}
        self.event_handlers = {}
        self._logged = set()
        self.on_connection_closed = None
        self.on_change = on_change   # called with no args when hubs connect/disconnect or talk
        self.last_contact_time = None

    def log_once(self, key, msg):
        """Log at INFO the first time per bridge run, DEBUG afterwards. Every
        home hub (Apple TV and HomePods) connects and retries, so per-event
        INFO lines flood the Indigo log."""
        if key in self._logged:
            _dbg(msg)
        else:
            self._logged.add(key)
            _LOGGER.info(msg)

    def last_contact(self):
        self.last_contact_time = time.time()
        self._changed()

    def _changed(self):
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:
                _dbg("HDS change callback failed", exc_info=True)

    def _listen(self, local_address):
        """Listen on local_address (synchronously, so the port can go straight
        back in the SetupDataStreamTransport write response)."""
        got = self.listeners.get(local_address)
        if got is not None:
            return got[1]
        family = socket.AF_INET6 if ":" in local_address else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((local_address, 0))
            sock.listen(4)
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise
        port = sock.getsockname()[1]
        entry = [None, port, sock]
        self.listeners[local_address] = entry

        async def start():
            entry[0] = await asyncio.start_server(self._on_connection, sock=sock)
        self.loop.create_task(start())
        _dbg("[%s] HDS: listening for the hub on %s port %d", self.name, local_address, port)
        return port

    def prepare(self, shared_secret, controller_salt, hub_address, local_address):
        """Create keys for an expected connection from hub_address; returns (port, accessory_salt)."""
        accessory_salt = os.urandom(32)
        a2c, c2a = derive_keys(shared_secret, controller_salt, accessory_salt)
        port = self._listen(local_address)
        now = time.monotonic()
        self.prepared = [p for p in self.prepared if now - p.created < PREPARED_TIMEOUT]
        self.prepared.append(_Prepared(a2c, c2a, hub_address))
        return port, accessory_salt

    async def _on_connection(self, reader, writer):
        peer = writer.get_extra_info("peername")
        host = peer[0] if peer else None
        now = time.monotonic()
        self.prepared = [p for p in self.prepared if now - p.created < PREPARED_TIMEOUT]
        candidates = [p for p in self.prepared if p.label == host]
        if not candidates or len(self.connections) >= MAX_CONNECTIONS:
            _dbg("[%s] HDS: refused connection from %s (%s)", self.name, peer,
                          "no session prepared for it" if not candidates else "too many connections")
            writer.close()
            return
        try:
            head = await asyncio.wait_for(reader.readexactly(4), HELLO_TIMEOUT)
            length = int.from_bytes(head[1:4], "big")
            if head[0] != 1 or length > MAX_PAYLOAD:
                raise ValueError("bad first frame")
            body = await asyncio.wait_for(reader.readexactly(length + 16), HELLO_TIMEOUT)
        except Exception:
            writer.close()
            return
        # Work out which prepared session this connection belongs to by
        # trying to decrypt its first frame (as HAP-NodeJS does).
        match = None
        for p in candidates:
            try:
                p.c2a.decrypt(_nonce(0), body, head)
                match = p
                break
            except Exception:
                continue
        if match is None:
            _LOGGER.warning("[%s] HDS: connection from %s didn't match a prepared session", self.name, host)
            writer.close()
            return
        if match in self.prepared:
            self.prepared.remove(match)
        # Re-feed the first frame through the normal reader
        feeder = asyncio.StreamReader()
        feeder.feed_data(head + body)
        conn = HDSConnection(self, _ChainedReader(feeder, reader), writer, match)
        self.connections.append(conn)
        _dbg("[%s] HDS: connection from %s matched", self.name, host)
        self._changed()
        await conn.run()

    def connection_closed(self, conn):
        if conn in self.connections:
            self.connections.remove(conn)
        if self.on_connection_closed is not None:
            try:
                self.on_connection_closed(conn)
            except Exception:
                _dbg("HDS connection-closed callback failed", exc_info=True)
        self._changed()

    def close(self):
        for c in list(self.connections):
            try:
                c.writer.close()
            except Exception:
                pass
        for server, _port, sock in self.listeners.values():
            if server is not None:
                server.close()
            else:
                sock.close()
        self.listeners.clear()
        self.prepared = []


class _ChainedReader:
    """Reads from a pre-filled buffer first, then the live socket."""

    def __init__(self, first, second):
        self.first = first
        self.second = second
        self.first_done = False

    async def readexactly(self, n):
        out = b""
        if not self.first_done:
            buffered = len(self.first._buffer)  # noqa: SLF001
            if buffered:
                take = min(n, buffered)
                out = await self.first.readexactly(take)
                n -= take
            if not len(self.first._buffer):  # noqa: SLF001
                self.first_done = True
        if n:
            out += await self.second.readexactly(n)
        return out
