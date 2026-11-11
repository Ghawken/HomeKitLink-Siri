"""
Subprocess worker for the audio proxy.

This module is invoked as ``python -m homekit_audio_proxy`` and runs the
blocking UDP recv/send loop. The SRTP key is read from stdin to avoid
exposing it in process arguments.

Two-way audio (talkback, from PR #42):
The socket that sends audio to the HomeKit client is bound to the same port
the client sends *its* microphone audio to (pyhap answers Setup Endpoints
with the client's own port). When a talkback target is supplied, incoming
SRTP from the client is decrypted, its RTP timestamps are converted back to
the 48 kHz Opus clock, and the plain RTP is forwarded to the camera's
speaker. For UniFi Protect the target comes from the Protect integration API
(POST .../cameras/{id}/talkback-session), which returns rtp://<camera>:7004
(Opus). Protect sessions are short-lived, so a fresh one is opened when talk
audio starts, and again if the camera starts rejecting packets.
"""

from __future__ import annotations

import json
import os
import select
import signal
import socket
import ssl
import struct
import sys
import time
import traceback
import urllib.parse
import urllib.request

from ._srtp import SRTPContext, SRTPDecryptContext

SRTP_OPUS_CLOCK_RATE = 48000
_UINT32_BE = struct.Struct("!I")
_RECV_TIMEOUT_SECONDS = 5.0
_MIN_RTP_HEADER_SIZE = 12
_UDP_MAX_READ = 2048
_TALKBACK_PAYLOAD_TYPE = 96          # what FFmpeg uses for Opus; Protect accepts it
_TALKBACK_RETRY_SECONDS = 2.0
_TALKBACK_IDLE_SECONDS = 3.0         # a gap this long means a new "talk"
# Echo suppression: while the Home app user is speaking, a doorbell's microphone
# picks their voice back up from its own speaker. Opus packets carrying speech are
# much bigger than near-silent ones, so packet size is a cheap voice detector.
# While speech was heard recently, audio going back to the phone is replaced with
# Opus silence (half-duplex ducking).
_OPUS_SILENCE = b"\xf8\xff\xfe"     # a valid 20 ms Opus frame that decodes to silence


def _log(level: str, msg: str) -> None:
    """Lines go to stderr; the parent maps the first word to a log level."""
    sys.stderr.write(f"{level} {msg}\n")
    sys.stderr.flush()


class _Talkback:
    """Forwards decrypted HomeKit microphone audio to a camera speaker."""

    def __init__(self, cfg: dict, srtp_key_b64: str, source_clock_rate: int) -> None:
        self._cfg = cfg
        self._decrypt = SRTPDecryptContext(srtp_key_b64)
        self._source_clock = source_clock_rate or 24000
        self._sock: socket.socket | None = None
        self._last_attempt = 0.0
        self._last_packet = 0.0
        self._forwarded = 0
        self._received = 0
        self._bad = 0
        self._name = cfg.get("name", "camera")
        self.echo_suppress = bool(cfg.get("echo_suppress", True))
        self._speech_bytes = int(cfg.get("speech_bytes", 24))
        self._hold = float(cfg.get("echo_hold_ms", 700)) / 1000.0
        self.last_speech = 0.0
        self._sizes = []
        self.ducked = 0

    def ducking(self, now: float) -> bool:
        return self.echo_suppress and (now - self.last_speech) < self._hold

    def _open_session(self) -> None:
        self._close()
        self._last_attempt = time.monotonic()
        url = "https://{}/proxy/protect/integration/v1/cameras/{}/talkback-session".format(
            self._cfg["host"], self._cfg["camera_id"])
        req = urllib.request.Request(url, data=b"", method="POST", headers={
            "X-API-KEY": self._cfg["api_key"], "Accept": "application/json"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  ## Protect consoles use a self-signed certificate
        try:
            with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
                info = json.loads(resp.read().decode())
            target = urllib.parse.urlsplit(info["url"])
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((target.hostname, target.port or 7004))
            sock.setblocking(False)
            self._sock = sock
            _log("INFO", f"Two-way audio: talking to {self._name} ({info.get('codec')}, "
                         f"{info.get('samplingRate')} Hz, {target.hostname}:{target.port})")
        except Exception as err:  # noqa: BLE001
            _log("WARNING", f"Two-way audio: couldn't open a Protect talkback session for {self._name}: {err}")

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def handle(self, data: bytes) -> None:
        if len(data) < _MIN_RTP_HEADER_SIZE or (data[0] >> 6) != 2:
            return
        if 200 <= data[1] <= 204:          # SRTCP from the client - ignore
            return
        self._received += 1
        rtp = self._decrypt.decrypt(data)
        if rtp is None:
            self._bad += 1
            if self._bad == 1:
                _log("WARNING", f"Two-way audio: Home app audio for {self._name} failed to decrypt")
            return
        now = time.monotonic()
        # Payload size -> "is the user speaking?" (echo suppression)
        hl = _MIN_RTP_HEADER_SIZE + (rtp[0] & 0x0F) * 4
        if (rtp[0] >> 4) & 1 and len(rtp) >= hl + 4:
            hl += 4 + int.from_bytes(rtp[hl + 2:hl + 4], "big") * 4
        payload_len = len(rtp) - hl
        if payload_len >= self._speech_bytes:
            self.last_speech = now
        if len(self._sizes) < 200:
            self._sizes.append(payload_len)
            if len(self._sizes) == 200:
                srt = sorted(self._sizes)
                _log("DEBUG", f"Two-way audio: talk packet sizes min {srt[0]} median {srt[100]} max {srt[-1]} "
                              f"(speech threshold {self._speech_bytes})")
        # Open a fresh Protect session at the start of each burst of talk,
        # since sessions expire shortly after they're created.
        if self._sock is None or (now - self._last_packet) > _TALKBACK_IDLE_SECONDS:
            if self._sock is not None:
                self._close()
            if now - self._last_attempt >= _TALKBACK_RETRY_SECONDS:
                self._open_session()
        self._last_packet = now
        if self._sock is None:
            return
        packet = bytearray(rtp)
        ts = _UINT32_BE.unpack_from(packet, 4)[0]
        _UINT32_BE.pack_into(packet, 4, (ts * SRTP_OPUS_CLOCK_RATE // self._source_clock) & 0xFFFFFFFF)
        packet[1] = (packet[1] & 0x80) | _TALKBACK_PAYLOAD_TYPE
        try:
            self._sock.send(bytes(packet))
            self._forwarded += 1
            if self._forwarded == 1:
                _log("DEBUG", f"Two-way audio: first packet sent to {self._name}")
        except BlockingIOError:
            pass
        except OSError as err:
            # The camera rejected us (expired session): reopen on the next packet
            _log("DEBUG", f"Two-way audio: send failed ({err}); reopening session")
            self._close()

    def close(self) -> None:
        if self.ducked:
            _log("DEBUG", f"Two-way audio: muted {self.ducked} return-audio packets while you were talking")
        if self._forwarded:
            _log("INFO", f"Two-way audio: finished, {self._forwarded} packets sent to {self._name}")
        elif self._received:
            _log("WARNING", f"Two-way audio: received {self._received} Home app packets for {self._name} but sent none")
        self._close()


def _exit_on_sigterm(signum, frame):  # noqa: ARG001
    """Stop cleanly so the ``finally`` below runs (and logs the talk summary)."""
    raise SystemExit(0)


def run_proxy(
    dest_addr: str,
    dest_port: int,
    srtp_key_b64: str,
    target_clock_rate: int,
    talkback: dict | None = None,
) -> int:
    """
    Run the audio proxy loop (blocking, for subprocess use).

    Returns exit code: 0 for clean shutdown, 1 for error.
    """
    try:
        srtp = SRTPContext(srtp_key_b64)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1

    talk: _Talkback | None = None
    if talkback:
        try:
            talk = _Talkback(talkback, srtp_key_b64, target_clock_rate)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            talk = None

    parent_pid = os.getppid()
    signal.signal(signal.SIGTERM, _exit_on_sigterm)

    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        recv_sock.bind(("127.0.0.1", 0))
        local_port = recv_sock.getsockname()[1]
    except OSError:
        traceback.print_exc(file=sys.stderr)
        recv_sock.close()
        return 1

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # SO_REUSEADDR allows quick rebind if a previous proxy just released
        # the port (e.g. stream restart)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to 0.0.0.0 so the kernel picks the correct source IP
        # for the route to the HomeKit client
        send_sock.bind(("0.0.0.0", dest_port))  # noqa: S104
    except OSError:
        traceback.print_exc(file=sys.stderr)
        send_sock.close()
        recv_sock.close()
        return 1

    # Signal the local port to the parent process
    sys.stdout.write(f"{local_port}\n")
    sys.stdout.flush()

    dest = (dest_addr, dest_port)
    packets_forwarded = 0
    allowed_sender: tuple[str, int] | None = None
    allowed_rtcp_sender: tuple[str, int] | None = None
    watch = [recv_sock, send_sock] if talk else [recv_sock]
    try:
        while True:
            readable, _, _ = select.select(watch, [], [], _RECV_TIMEOUT_SECONDS)
            if not readable:
                # Check if parent process is still alive to avoid orphaning
                if os.getppid() != parent_pid:
                    break
                continue

            if talk and send_sock in readable:
                try:
                    data, sender = send_sock.recvfrom(_UDP_MAX_READ)
                except OSError:
                    data, sender = b"", None
                # Only accept audio from the HomeKit client (or Home hub) of this stream
                if data and sender and sender[0] == dest_addr:
                    try:
                        talk.handle(data)
                    except Exception:
                        traceback.print_exc(file=sys.stderr)

            if recv_sock not in readable:
                continue
            data, sender = recv_sock.recvfrom(_UDP_MAX_READ)
            if len(data) < _MIN_RTP_HEADER_SIZE:
                continue

            # RTCP (muxed on the same port, RFC 5761): packet types 200-204.
            # FFmpeg sends RTCP from a different local socket than RTP, so each is
            # locked to its own first sender (stops other local processes injecting).
            if 200 <= data[1] <= 204:
                if allowed_rtcp_sender is None:
                    allowed_rtcp_sender = sender
                elif sender != allowed_rtcp_sender:
                    continue
                packet = bytearray(data)
                if data[1] == 200 and len(data) >= 20:
                    # Sender report: rescale its RTP timestamp to match the RTP packets
                    ts = _UINT32_BE.unpack_from(data, 16)[0]
                    _UINT32_BE.pack_into(packet, 16, (ts * target_clock_rate // SRTP_OPUS_CLOCK_RATE) & 0xFFFFFFFF)
                send_sock.sendto(srtp.encrypt_rtcp(bytes(packet)), dest)
                continue

            # Lock to the first sender (FFmpeg) to prevent other local
            # processes from injecting audio into the stream.
            if allowed_sender is None:
                allowed_sender = sender
            elif sender != allowed_sender:
                continue

            # Convert timestamp from 48000 Hz to negotiated sample rate
            ts = _UINT32_BE.unpack_from(data, 4)[0]
            new_ts = (ts * target_clock_rate // SRTP_OPUS_CLOCK_RATE) & 0xFFFFFFFF
            packet = bytearray(data)
            _UINT32_BE.pack_into(packet, 4, new_ts)

            # Echo suppression: silence the camera's audio while the user talks
            if talk is not None and talk.ducking(time.monotonic()):
                hl = _MIN_RTP_HEADER_SIZE + (packet[0] & 0x0F) * 4
                packet = packet[:hl] + _OPUS_SILENCE
                talk.ducked += 1

            srtp_packet = srtp.encrypt(bytes(packet))
            send_sock.sendto(srtp_packet, dest)
            packets_forwarded += 1
    except OSError as err:
        sys.stderr.write(
            f"Audio proxy socket error after {packets_forwarded} packets: {err}\n"
        )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        if talk is not None:
            talk.close()
        recv_sock.close()
        send_sock.close()

    return 0
