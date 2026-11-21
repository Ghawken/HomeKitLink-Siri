"""Talk through a speaker: the Home app's talk audio as a live stream to an Apple TV / HomePod or a Sonos.

The audio proxy forwards the decrypted talk audio (Opus RTP) to a local UDP port here. On the first
packet of a talk, ffmpeg (the plugin's own) is started to turn it into a live MP3 stream, served over
HTTP from this Mac, and the Apple TV plugin (com.GlennNZ.indigoplugin.appleTV) is asked to play that
URL with its existing Send Command action: pyatv's stream_file plays a live HTTP stream (it's an
internet-radio client). A Sonos (Sonos plugin) is asked to play it as an audio clip, the speaker's own
announcement API that Home Assistant uses: it lowers the music, plays, then resumes. When the talk stops for a few seconds the stream ends, so the device stops;
the next talk starts a new stream. Everything closes with the live view.

Delay: pyatv waits for 32 KB before playing (0.8 s at 320 kbps, hence the high bitrate), then
AirPlay's own ~1.5 s, plus connecting. Expect 2-3 s.
"""

import base64
import json
import logging
import os
import ssl
import struct
import secrets
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import indigo
except ImportError:
    pass

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

APPLETV_PLUGIN_ID = "com.GlennNZ.indigoplugin.appleTV"
SONOS_PLUGIN_ID = "com.ssi.indigoplugin.Sonos"
SONOS_API_KEY = "123e4567-e89b-12d3-a456-426655440000"   ## Sonos's public key for the local control API (as HA uses)
IDLE_SECONDS = 2.5          ## no talk for this long ends the current stream
FFMPEG_WARMUP = 0.6         ## packets are held this long while ffmpeg starts listening
BITRATE = "320k"            ## pyatv reads 32 KB before playing: higher bitrate = sooner


def is_airplay_target(dev):
    """An Apple TV plugin device that takes AirPlay audio (Apple TV, HomePod)."""
    try:
        return dev.pluginId == APPLETV_PLUGIN_ID and int(dev.states.get("RAOPPort", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def is_sonos_target(dev):
    """A Sonos plugin player with an address and player id."""
    return (dev.pluginId == SONOS_PLUGIN_ID and dev.deviceTypeId == "ZonePlayer"
            and bool(str(dev.address or "").strip()) and str(dev.states.get("ZP_LocalUID", "")).startswith("RINCON"))


def is_stream_target(dev):
    return is_airplay_target(dev) or is_sonos_target(dev)


def airplay_targets():
    items = [(d.id, d.name) for d in indigo.devices.iter(APPLETV_PLUGIN_ID) if is_airplay_target(d)]
    return sorted(items, key=lambda x: x[1].lower())


def sonos_targets():
    items = [(d.id, d.name) for d in indigo.devices.iter(SONOS_PLUGIN_ID) if is_sonos_target(d)]
    return sorted(items, key=lambda x: x[1].lower())


def sonos_audio_clip(address, player_id, url, timeout=5, on_status=None, listen=8.0):
    """Ask a Sonos to play url as an audio clip (local websocket API on port 1443, audioClip:1
    loadAudioClip). Returns (ok, detail). After it's accepted, on_status gets the clip's status events
    for up to `listen` seconds (in a background thread), so a clip that fails to play is reported."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   ## Sonos players use a self-signed certificate
    raw = socket.create_connection((address, 1443), timeout=timeout)
    sock = ctx.wrap_socket(raw, server_hostname=address)
    handed_off = False
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(("GET /websocket/api HTTP/1.1\r\nHost: {}:1443\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      "Sec-WebSocket-Key: {}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: v1.api.smartspeaker.audio\r\n"
                      "X-Sonos-Api-Key: {}\r\n\r\n").format(address, key, SONOS_API_KEY).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1024)
            if not chunk:
                return False, "connection closed"
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            return False, head.split(b"\r\n", 1)[0].decode(errors="replace")
        message = json.dumps([{"namespace": "audioClip:1", "command": "loadAudioClip", "playerId": player_id, "cmdId": "1"},
                              {"name": "HomeKitLink talk", "appId": "com.GlennNZ.indigoplugin.HomeKitLink-Siri",
                               "streamUrl": url, "clipType": "CUSTOM", "priority": "HIGH"}]).encode()
        mask = os.urandom(4)
        header = bytes([0x81]) + (bytes([0x80 | len(message)]) if len(message) < 126 else bytes([0x80 | 126]) + struct.pack("!H", len(message)))
        sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(message)))
        ## The reply: one text frame (unmasked from the server)
        def read(n):
            data = b""
            while len(data) < n:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    raise OSError("connection closed")
                data += chunk
            return data
        def frame():
            b1, b2 = read(2)
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", read(8))[0]
            data = read(length)
            return b1 & 0x0F, data
        while True:
            opcode, data = frame()
            if opcode == 1:
                break
        reply = json.loads(data.decode(errors="replace"))
        head_obj = reply[0] if isinstance(reply, list) and reply else {}
        if head_obj.get("success"):
            if on_status is not None:
                def watch():
                    end = time.monotonic() + listen
                    try:
                        while time.monotonic() < end:
                            sock.settimeout(max(0.1, end - time.monotonic()))
                            op, raw_msg = frame()
                            if op != 1:
                                continue
                            msg = json.loads(raw_msg.decode(errors="replace"))
                            body = msg[1] if isinstance(msg, list) and len(msg) > 1 else {}
                            if isinstance(body, dict) and (body.get("_objectType") == "audioClip" or body.get("errorCode")):
                                on_status(body)
                    except (OSError, ValueError):
                        pass
                    finally:
                        try:
                            sock.close()
                        except OSError:
                            pass
                handed_off = True   ## the watcher reads and closes it
                threading.Thread(target=watch, name="HKLS-sonos-clip", daemon=True).start()
            return True, ""
        body = reply[1] if isinstance(reply, list) and len(reply) > 1 else reply
        return False, str(body.get("errorCode") or body.get("reason") or body)[:200] if isinstance(body, dict) else str(body)[:200]
    finally:
        if not handed_off:
            try:
                sock.close()
            except OSError:
                pass


def _free_port(kind):
    s = socket.socket(socket.AF_INET, kind)
    s.bind(("0.0.0.0" if kind == socket.SOCK_STREAM else "127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _local_ip_towards(address):
    """This Mac's address on the route to the device (what it can reach us on)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((address, 9))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


DEFAULT_HTTP_PORT = 8891   ## a fixed port, so a router can allow speakers on another subnet / VLAN to reach it
FETCH_WAIT = 6.0           ## the speaker should fetch the stream within this long of being asked

_server = None
_server_lock = threading.Lock()
_streams = {}              ## token -> TalkStream


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def _stream(self):
        name = self.path.split("?", 1)[0].rsplit("/", 1)[-1]
        if name.startswith("talk-") and name.endswith(".mp3"):
            return _streams.get(name[5:-4])
        return None

    def do_GET(self):
        stream = self._stream()
        if stream is None:
            self.send_error(404)
            return
        stream._serve(self)

    def do_HEAD(self):
        if self._stream() is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.end_headers()


def _shared_server(plugin):
    """One HTTP server for every talk stream, on the Plugin Config port (falls back to any free port)."""
    global _server
    with _server_lock:
        if _server is not None:
            return _server
        try:
            port = int(getattr(plugin, "talkStreamPort", DEFAULT_HTTP_PORT) or DEFAULT_HTTP_PORT)
        except (TypeError, ValueError):
            port = DEFAULT_HTTP_PORT
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
        except OSError as err:
            plugin.logger.warning("Talk streams: port {} isn't free ({}), using another. Speakers on another subnet "
                                  "need a fixed port: choose a free one in Plugin Config.".format(port, err))
            server = ThreadingHTTPServer(("0.0.0.0", 0), _Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, name="HKLS-talk-http", daemon=True).start()
        _server = server
        return server


def stop_server():
    """Plugin shutdown, or the port changed in Plugin Config."""
    global _server
    with _server_lock:
        server, _server = _server, None
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass


class TalkStream:
    """One live view's talk to a speaker (HomePod / Apple TV, or Sonos)."""

    def __init__(self, plugin, target_id, camera_name):
        self.plugin = plugin
        self.target_id = int(target_id)
        self.camera_name = camera_name
        target = indigo.devices[self.target_id]
        self.target_name = target.name
        self.sonos = is_sonos_target(target)
        self.sonos_address = str(target.address or "").strip()
        self.sonos_player = str(target.states.get("ZP_LocalUID", ""))
        self.host = _local_ip_towards(str(target.pluginProps.get("IP", "") or target.address or "")) \
            or (plugin.HAPAdvertised_ipaddress or [None])[0] or _local_ip_towards("192.168.0.1") or "127.0.0.1"
        self.token = secrets.token_urlsafe(8)
        self._lock = threading.Condition()
        self._closed = False
        self._ffmpeg = None
        self._ffmpeg_port = None
        self._pending = []           ## packets held while ffmpeg starts
        self._ffmpeg_ready_at = 0.0
        self._burst = None           ## {"data": bytearray, "done": bool, "n": int}
        self._bursts = 0
        self._last_audio = 0.0
        ## Talk audio from the proxy worker
        self._rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx.bind(("127.0.0.1", 0))
        self.rtp_port = self._rx.getsockname()[1]
        self._tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ## HTTP for the speaker: the shared server, this stream's own path
        self.http_port = _shared_server(plugin).server_address[1]
        self.url = "http://{}:{}/talk-{}.mp3".format(self.host, self.http_port, self.token)
        _streams[self.token] = self
        for target_fn, name in ((self._receive, "rx"), (self._watch, "idle")):
            threading.Thread(target=target_fn, name="HKLS-talk-" + name, daemon=True).start()

    def worker_config(self):
        """What the audio proxy worker needs: forward talk RTP here."""
        return {"forward": ["127.0.0.1", self.rtp_port], "name": self.target_name}

    # --- talk audio in -> ffmpeg -------------------------------------------------
    def _receive(self):
        while not self._closed:
            try:
                data = self._rx.recv(2048)
            except OSError:
                return
            if self._closed:
                return
            now = time.monotonic()
            self._last_audio = now
            if self._ffmpeg is None:
                try:
                    self._start_ffmpeg()
                except Exception:
                    self.plugin.logger.exception("[{}] Talk to '{}': couldn't start ffmpeg".format(self.camera_name, self.target_name))
                    return
            if now < self._ffmpeg_ready_at:
                self._pending.append(data)
                continue
            if self._pending:
                for p in self._pending:
                    self._tx.sendto(p, ("127.0.0.1", self._ffmpeg_port))
                self._pending = []
            self._tx.sendto(data, ("127.0.0.1", self._ffmpeg_port))

    def _start_ffmpeg(self):
        self._ffmpeg_port = _free_port(socket.SOCK_DGRAM)
        sdp = ("v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=HomeKitLink talk\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\n"
               "m=audio {} RTP/AVP 96\r\na=rtpmap:96 opus/48000/2\r\n").format(self._ffmpeg_port)
        sdp_path = os.path.join(self.plugin.pluginprefDirectory, "talk-{}.sdp".format(self.token))
        with open(sdp_path, "w") as f:
            f.write(sdp)
        self._sdp_path = sdp_path
        cmd = [self.plugin.ffmpeg_command_line, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-protocol_whitelist", "file,udp,rtp", "-fflags", "nobuffer", "-flags", "low_delay",
               "-i", sdp_path, "-vn", "-c:a", "libmp3lame", "-b:a", BITRATE, "-ar", "44100", "-ac", "2",
               "-flush_packets", "1", "-id3v2_version", "0", "-write_xing", "0", "-f", "mp3", "pipe:1"]
        _LOGGER.debug("[%s] Talk to %s: %s", self.camera_name, self.target_name, " ".join(cmd))
        self._ffmpeg = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._ffmpeg_ready_at = time.monotonic() + FFMPEG_WARMUP
        threading.Thread(target=self._read_ffmpeg, args=(self._ffmpeg,), name="HKLS-talk-mp3", daemon=True).start()
        threading.Thread(target=self._ffmpeg_errors, args=(self._ffmpeg,), name="HKLS-talk-err", daemon=True).start()

    def _ffmpeg_errors(self, proc):
        for line in proc.stderr:
            text = line.decode(errors="replace").strip()
            if text:
                _LOGGER.debug("[%s] Talk ffmpeg: %s", self.camera_name, text)

    # --- ffmpeg MP3 out -> bursts --------------------------------------------------
    def _read_ffmpeg(self, proc):
        while not self._closed:
            chunk = proc.stdout.read1(8192) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
            if not chunk:
                break
            start = False
            with self._lock:
                if self._burst is None or self._burst["done"]:
                    self._bursts += 1
                    self._burst = {"data": bytearray(), "done": False, "n": self._bursts}
                    start = True
                self._burst["data"] += chunk
                self._lock.notify_all()
            if start:   ## its own thread: a slow speaker mustn't hold up reading ffmpeg
                threading.Thread(target=self._play, name="HKLS-talk-play", daemon=True).start()

    def _watch(self):
        """End the stream when the talk stops, so the device stops playing. ffmpeg stops too: the next
        talk starts a fresh one (and a fresh MP3 stream), whatever Home does to its RTP in between."""
        while not self._closed:
            time.sleep(0.5)
            if self._ffmpeg is None or time.monotonic() - self._last_audio <= IDLE_SECONDS:
                continue
            with self._lock:
                if self._burst is not None and not self._burst["done"]:
                    self._burst["done"] = True
                    self._lock.notify_all()
            self._stop_ffmpeg()

    def _stop_ffmpeg(self):
        proc, self._ffmpeg = self._ffmpeg, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _play(self):
        """Ask the speaker to play the stream: a Sonos directly (audio clip), an Apple TV / HomePod through
        the Apple TV plugin (its Send Command action: stream_file=<url>)."""
        with self._lock:
            burst = self._burst
        threading.Thread(target=self._check_fetched, args=(burst,), name="HKLS-talk-check", daemon=True).start()
        if self.sonos:
            try:
                ok, detail = sonos_audio_clip(self.sonos_address, self.sonos_player, self.url,
                                              on_status=lambda st: self._sonos_status(st))
            except Exception as err:
                ok, detail = False, str(err)
            if ok:
                self.plugin.logger.info("[{}] Talk: streaming to '{}'".format(self.camera_name, self.target_name))
            else:
                self.plugin.logger.warning("[{}] Talk to Sonos '{}' ({}): it didn't accept the audio clip: {}. "
                                           "Audio clips need a Sonos S2 speaker that supports them.".format(
                                               self.camera_name, self.target_name, self.sonos_address, detail))
            return
        try:
            atv = indigo.server.getPlugin(APPLETV_PLUGIN_ID)
            if not atv.isEnabled():
                self.plugin.logger.warning("[{}] Talk to '{}': the Apple TV plugin isn't enabled.".format(self.camera_name, self.target_name))
                return
            self.plugin.logger.info("[{}] Talk: streaming to '{}'".format(self.camera_name, self.target_name))
            atv.executeAction("sendCommand", props={"appleTV": str(self.target_id), "command": "stream_file", "args": self.url})
        except Exception:
            self.plugin.logger.exception("[{}] Talk to '{}': couldn't start the stream".format(self.camera_name, self.target_name))

    def _check_fetched(self, burst):
        """A speaker that's asked to play but never fetches the stream is almost always a firewall /
        VLAN between it and this Mac: say so (once per live view)."""
        time.sleep(FETCH_WAIT)
        if burst is None or burst.get("fetched") or self._closed or getattr(self, "_fetch_warned", False):
            return
        self._fetch_warned = True
        self.plugin.logger.warning(
            "[{}] Talk: '{}' was asked to play {} but never fetched it. If it's on another subnet or VLAN, "
            "allow tcp/{} from it to this Mac ({}) on your router / firewall (the port is set in Plugin Config).".format(
                self.camera_name, self.target_name, self.url.rsplit("/", 1)[0], self.http_port, self.host))

    def _sonos_status(self, status):
        """Audio clip events from the Sonos after it accepted the clip (e.g. it couldn't play the stream)."""
        state = str(status.get("status", ""))
        error = status.get("errorCode") or status.get("error")
        _LOGGER.debug("[%s] Talk: Sonos '%s' clip %s %s", self.camera_name, self.target_name, state, error or "")
        if error or state.upper() == "ERROR":
            self.plugin.logger.warning("[{}] Talk: Sonos '{}' couldn't play the stream: {}".format(
                self.camera_name, self.target_name, error or status))

    def _serve(self, handler):
        with self._lock:
            burst = self._burst
        if burst is None:
            handler.send_error(404)
            return
        burst["fetched"] = handler.client_address[0]
        _LOGGER.debug("[%s] Talk: %s (%s) is fetching the stream", self.camera_name, self.target_name, handler.client_address[0])
        handler.send_response(200)
        handler.send_header("Content-Type", "audio/mpeg")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        sent = 0
        try:
            while True:
                with self._lock:
                    while sent >= len(burst["data"]) and not burst["done"] and not self._closed:
                        self._lock.wait(1.0)
                    chunk = bytes(burst["data"][sent:])
                    finished = (burst["done"] or self._closed) and sent + len(chunk) >= len(burst["data"])
                if chunk:
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
                    sent += len(chunk)
                if finished:
                    return
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    # --- end of the live view --------------------------------------------------------
    def close(self):
        if self._closed:
            return
        self._closed = True
        with self._lock:
            if self._burst is not None:
                self._burst["done"] = True
            self._lock.notify_all()
        for s in (self._rx, self._tx):
            try:
                s.close()
            except OSError:
                pass
        self._stop_ffmpeg()
        _streams.pop(self.token, None)
        try:
            if getattr(self, "_sdp_path", None):
                os.remove(self._sdp_path)
        except OSError:
            pass
        if self._bursts:
            _LOGGER.debug("[%s] Talk to %s: %d stream(s)", self.camera_name, self.target_name, self._bursts)
