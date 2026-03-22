"""
HomeKit audio RTP proxy.

FFmpeg's RTP muxer uses a 48000 Hz clock rate for Opus (per RFC 7587),
but Apple's HomeKit implementation expects the RTP timestamps to use
the negotiated sample rate (e.g., 16000 Hz). This library provides a
subprocess-based proxy that receives plain RTP from FFmpeg, converts
the timestamps, encrypts with SRTP, and forwards to the HomeKit client.

https://github.com/bdraco/homekit-audio-proxy/releases

Very slight modification to allow pythonpath to be passed.

"""

__version__ = "1.2.1-indigo"

from .proxy import AudioProxy

__all__ = ["AudioProxy"]
