"""Async AudioProxy that manages the subprocess."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from ._worker import SRTP_OPUS_CLOCK_RATE

_LOGGER = logging.getLogger(__name__)


class AudioProxy:
    """
    Proxy that converts FFmpeg's Opus RTP timestamps for HomeKit.

    Runs as a subprocess to keep crypto work off the caller's event loop.
    """

    def __init__(
        self,
        dest_addr: str,
        dest_port: int,
        srtp_key_b64: str,
        target_clock_rate: int,
        python_path: str | None = None,
    ) -> None:
        """Initialize the audio proxy.

        Args:
            python_path: Path to the Python interpreter to use for the
                subprocess. Defaults to sys.executable. Indigo and other
                embedded hosts should pass the real Python 3 path here
                (e.g. sys.prefix + "/bin/python3").
        """
        self._dest_addr = dest_addr
        self._dest_port = dest_port
        self._srtp_key_b64 = srtp_key_b64
        self._target_clock_rate = target_clock_rate
        self._python_path = python_path or sys.executable
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self.local_port: int = 0

    async def async_start(self) -> None:
        """Start the proxy subprocess."""
        python = self._python_path
        # Verify the interpreter exists before spawning
        if not os.path.isfile(python):
            _LOGGER.error(
                "Audio proxy python interpreter not found: %s", python
            )
            return

        _LOGGER.debug(
            "Audio proxy launching subprocess: %s -m homekit_audio_proxy %s %s %s",
            python,
            self._dest_addr,
            self._dest_port,
            self._target_clock_rate,
        )

        self._process = await asyncio.create_subprocess_exec(
            python,
            "-m",
            "homekit_audio_proxy",
            self._dest_addr,
            str(self._dest_port),
            str(self._target_clock_rate),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Pass SRTP key via stdin to avoid exposing it in process args
        if self._process.stdin:
            self._process.stdin.write(self._srtp_key_b64.encode() + b"\n")
            await self._process.stdin.drain()
            self._process.stdin.close()

        if self._process.stdout is None:
            _LOGGER.error("Audio proxy subprocess has no stdout")
            await self.async_stop()
            return

        line = await self._process.stdout.readline()
        if not line:
            # Process exited before writing the port — read stderr for details
            stderr_output = b""
            if self._process.stderr:
                stderr_output = await self._process.stderr.read()
            _LOGGER.error(
                "Audio proxy subprocess failed to start: %s",
                stderr_output.decode(errors="replace").strip(),
            )
            await self.async_stop()
            return

        self.local_port = int(line.strip())

        # Log stderr in the background so errors are visible
        if self._process.stderr:
            self._stderr_task = asyncio.create_task(
                self._log_stderr(self._process.stderr)
            )

        _LOGGER.debug(
            "Audio proxy subprocess started (PID %d) on port %d -> %s:%d"
            " (clock %d->%d)",
            self._process.pid,
            self.local_port,
            self._dest_addr,
            self._dest_port,
            SRTP_OPUS_CLOCK_RATE,
            self._target_clock_rate,
        )

    @staticmethod
    async def _log_stderr(stderr: asyncio.StreamReader) -> None:
        """Forward subprocess stderr to logger."""
        while True:
            line = await stderr.readline()
            if not line:
                return
            _LOGGER.warning(
                "Audio proxy: %s",
                line.decode(errors="replace").rstrip(),
            )

    async def async_stop(self) -> None:
        """Stop the proxy subprocess and wait for port release."""
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None
        if self._process is not None:
            if self._process.returncode is None:
                self._process.kill()
                await self._process.wait()
            self._process = None