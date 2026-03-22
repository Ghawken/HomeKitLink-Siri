"""
Subprocess worker for the audio proxy.

This module is invoked as ``python -m homekit_audio_proxy`` and runs the
blocking UDP recv/send loop. The SRTP key is read from stdin to avoid
exposing it in process arguments.
"""

from __future__ import annotations

import os
import socket
import struct
import sys
import traceback

from ._srtp import SRTPContext

SRTP_OPUS_CLOCK_RATE = 48000
_UINT32_BE = struct.Struct("!I")
_RECV_TIMEOUT_SECONDS = 5.0
_MIN_RTP_HEADER_SIZE = 12
_UDP_MAX_READ = 2048


def run_proxy(
    dest_addr: str,
    dest_port: int,
    srtp_key_b64: str,
    target_clock_rate: int,
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

    parent_pid = os.getppid()

    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        recv_sock.settimeout(_RECV_TIMEOUT_SECONDS)
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
    try:
        while True:
            try:
                data, sender = recv_sock.recvfrom(_UDP_MAX_READ)
            except TimeoutError:
                # Check if parent process is still alive to avoid orphaning
                if os.getppid() != parent_pid:
                    break
                continue
            if len(data) < _MIN_RTP_HEADER_SIZE:
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
        recv_sock.close()
        send_sock.close()

    return 0
