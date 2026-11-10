"""HKSV stage 3: prebuffer and recording delivery over HomeKit Data Stream.

Modelled on HAP-NodeJS CameraRecordingStream (RecordingManagement.js) and
homebridge-unifi-protect's approach:

  * While recording is enabled and a configuration has been selected, one
    ffmpeg per camera encodes the camera stream into exactly the format the hub
    chose (H.264 profile/level/size/bitrate/keyframe interval, AAC-LC) as
    fragmented MP4, one fragment per keyframe interval. We keep the init
    segment and the last few fragments in memory (the prebuffer).
  * When a hub sends dataSend/open, we reply success, then send dataSend/data
    events: the init segment ("mediaInitialization"), the prebuffered
    fragments, then live fragments ("mediaFragment"), each split into chunks
    of at most 256 KiB. When motion has been clear for one fragment we mark the
    last fragment endOfStream; the hub then acks/closes.
"""

import asyncio
import collections
import logging
import time

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn.HKSV")

MAX_CHUNK = 0x40000
MAX_RECORDING_SECONDS = 300
RESTART_DELAY = 10


class Prebuffer:
    """Continuously encodes the camera into fMP4 in the hub's chosen format."""

    def __init__(self, name, ffmpeg, source, selected, loop, hw=False):
        self.hw = hw
        self.name = name
        self.ffmpeg = ffmpeg
        self.source = source
        self.sel = selected
        self.loop = loop
        self.init_segment = None
        self.fragments = collections.deque(maxlen=4)   # (time, bytes)
        self.subscribers = set()
        self.proc = None
        self.task = None
        self.running = False

    def _cmd(self):
        v, a = self.sel["video"], self.sel["audio"]
        w, h, fps = v["width"], v["height"], v["fps"] or 30
        gop = max(1, int(round(fps * max(1000, v["iframe_interval_ms"] or 4000) / 1000)))
        vbr = max(300, int(v["bitrate_kbps"] or 2000))
        abr = max(16, int(a["bitrate_kbps"] or 64))
        profile = v["profile"]
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats",
               *(["-rtsp_transport", "tcp"] if str(self.source).lower().startswith("rtsp") else []),
               "-i", self.source,
               "-map", "0:v:0", "-map", "0:a:0?",
               *(["-c:v", "h264_videotoolbox", "-realtime", "1", "-prio_speed", "1"] if self.hw else
                 ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                  "-x264-params", "sliced-threads=0:slices=1"]),
               "-profile:v", profile, "-level:v", v["level"], "-bf", "0",
               "-vf", "scale={w}:{h}:force_original_aspect_ratio=decrease,"
                      "pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1".format(w=w, h=h),
               "-pix_fmt", "yuv420p", "-r", str(fps),
               "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
               "-b:v", "{}k".format(vbr), "-maxrate", "{}k".format(vbr), "-bufsize", "{}k".format(vbr * 2),
               "-c:a", "aac", "-profile:a", "aac_low", "-ar", str(a["sample_rate"]), "-ac", str(a["channels"] or 1),
               "-b:a", "{}k".format(abr),
               "-f", "mp4", "-movflags", "frag_keyframe+empty_moov+default_base_moof",
               "pipe:1"]
        return cmd

    def start(self):
        if self.running:
            return
        self.running = True
        self.task = self.loop.create_task(self._run())

    def stop(self):
        self.running = False
        if self.proc is not None and self.proc.returncode is None:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
        if self.task is not None:
            self.task.cancel()

    async def _run(self):
        while self.running:
            try:
                self.init_segment = None
                self.fragments.clear()
                self.proc = await asyncio.create_subprocess_exec(
                    *self._cmd(), stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                _LOGGER.info("[%s] HKSV: prebuffer started (%dx%d@%d, %d kbps)", self.name,
                             self.sel["video"]["width"], self.sel["video"]["height"],
                             self.sel["video"]["fps"], self.sel["video"]["bitrate_kbps"])
                err_task = self.loop.create_task(self._drain_stderr(self.proc.stderr))
                await self._read_boxes(self.proc.stdout)
                await self.proc.wait()
                err_task.cancel()
            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.warning("[%s] HKSV: prebuffer error", self.name, exc_info=True)
            if self.running:
                _LOGGER.warning("[%s] HKSV: prebuffer ffmpeg stopped; restarting in %ds", self.name, RESTART_DELAY)
                await asyncio.sleep(RESTART_DELAY)

    async def _drain_stderr(self, stream):
        while True:
            line = await stream.readline()
            if not line:
                return
            _LOGGER.debug("[%s] HKSV prebuffer ffmpeg: %s", self.name, line.decode(errors="replace").rstrip())

    async def _read_boxes(self, stream):
        pending = []
        while True:
            head = await stream.readexactly(8)
            size = int.from_bytes(head[:4], "big")
            btype = head[4:8]
            if size == 1:
                ext = await stream.readexactly(8)
                size = int.from_bytes(ext, "big")
                body = await stream.readexactly(size - 16)
                box = head + ext + body
            else:
                body = await stream.readexactly(size - 8)
                box = head + body
            if btype in (b"ftyp", b"moov"):
                pending.append(box)
                if btype == b"moov":
                    self.init_segment = b"".join(pending)
                    pending = []
            elif btype == b"moof":
                pending = [box]
            elif btype == b"mdat":
                pending.append(box)
                frag = b"".join(pending)
                pending = []
                self.fragments.append((time.monotonic(), frag))
                for q in list(self.subscribers):
                    q.put_nowait(frag)
            else:
                # styp/sidx/etc. belong to the next fragment
                pending.append(box)

    def subscribe(self):
        q = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        self.subscribers.discard(q)


class RecordingSession:
    """One dataSend stream to one hub."""

    def __init__(self, recorder, conn, request_id, stream_id):
        self.r = recorder
        self.conn = conn
        self.request_id = request_id
        self.stream_id = stream_id
        self.closed = False
        self.task = None

    def close(self, reason=None):
        self.closed = True
        if self.task is not None:
            self.task.cancel()

    def _send_fragment(self, data, initialization, seq, is_last):
        offset, chunk_seq = 0, 1
        while offset < len(data) and not self.closed:
            part = data[offset:offset + MAX_CHUNK]
            offset += len(part)
            meta = {
                "dataType": "mediaInitialization" if initialization else "mediaFragment",
                "dataSequenceNumber": seq,
                "dataChunkSequenceNumber": chunk_seq,
                "isLastDataChunk": offset >= len(data),
            }
            if chunk_seq == 1:
                meta["dataTotalSize"] = len(data)
            event = {"streamId": self.stream_id, "packets": [{"data": part, "metadata": meta}]}
            if offset >= len(data):
                event["endOfStream"] = bool(is_last)
            self.conn.send_event("dataSend", "data", event)
            chunk_seq += 1

    async def run(self):
        pb = self.r.prebuffer
        name = self.r.name
        q = pb.subscribe()
        started = time.monotonic()
        sent = 0
        try:
            # Wait briefly for the encoder to have an init segment
            for _ in range(50):
                if pb.init_segment:
                    break
                await asyncio.sleep(0.1)
            if not pb.init_segment:
                _LOGGER.warning("[%s] HKSV: recording requested but the prebuffer isn't ready", name)
                self.conn.send_event("dataSend", "close", {"streamId": self.stream_id, "reason": 5})
                return
            self.conn.send_response("dataSend", "open", self.request_id, 0, {"status": 0})
            seq = 1
            self._send_fragment(pb.init_segment, True, seq, False)
            # Prebuffer: fragments from the last prebuffer window
            window = max(1.0, self.r.prebuffer_ms / 1000.0) + 0.5
            now = time.monotonic()
            for ts, frag in list(pb.fragments):
                if now - ts <= window + self.r.fragment_s:
                    seq += 1
                    self._send_fragment(frag, False, seq, False)
                    sent += 1
            _LOGGER.info("[%s] HKSV: recording to hub %s (stream %d, %d prebuffered fragment%s)", name,
                         self.conn.peer[0] if self.conn.peer else "?", self.stream_id, sent, "" if sent == 1 else "s")
            clear_since = None
            while not self.closed:
                frag = await asyncio.wait_for(q.get(), timeout=self.r.fragment_s * 3 + 5)
                motion = self.r.motion_active()
                if motion:
                    clear_since = None
                elif clear_since is None:
                    clear_since = time.monotonic()
                too_long = time.monotonic() - started > MAX_RECORDING_SECONDS
                last = too_long or (clear_since is not None and time.monotonic() - clear_since >= self.r.fragment_s)
                seq += 1
                self._send_fragment(frag, False, seq, last)
                sent += 1
                if last:
                    _LOGGER.info("[%s] HKSV: recording finished - %d fragments (%.0f s)", name, sent,
                                 time.monotonic() - started)
                    break
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            _LOGGER.warning("[%s] HKSV: no video from the prebuffer - closing recording", name)
            try:
                self.conn.send_event("dataSend", "close", {"streamId": self.stream_id, "reason": 5})
            except Exception:
                pass
        except Exception:
            _LOGGER.warning("[%s] HKSV: recording stream error", name, exc_info=True)
        finally:
            pb.unsubscribe(q)
            self.r.sessions.discard(self)


class Recorder:
    """Glue between HKSVRecording, the prebuffer and the HDS server."""

    def __init__(self, name, ffmpeg, source, loop, motion_getter, hw_getter=None):
        self.hw_getter = hw_getter or (lambda: False)
        self.name = name
        self.ffmpeg = ffmpeg
        self.source = source
        self.loop = loop
        self.motion_active = motion_getter
        self.prebuffer = None
        self.selected = None
        self.prebuffer_ms = 4000
        self.fragment_s = 4.0
        self.sessions = set()

    def configure(self, selected, enabled):
        """(Re)start or stop the prebuffer to match the hub's choices."""
        def apply():
            if self.prebuffer is not None and (not enabled or selected != self.selected):
                self.prebuffer.stop()
                self.prebuffer = None
            self.selected = selected
            if enabled and selected and self.source and self.prebuffer is None:
                self.prebuffer_ms = selected.get("prebuffer_ms") or 4000
                self.fragment_s = (selected.get("fragment_ms") or 4000) / 1000.0
                self.prebuffer = Prebuffer(self.name, self.ffmpeg, self.source, selected, self.loop,
                                           hw=bool(self.hw_getter()))
                self.prebuffer.start()
        self.loop.call_soon_threadsafe(apply)

    def attach(self, hds_server):
        hds_server.on_connection_closed = self._on_connection_closed
        hds_server.request_handlers[("dataSend", "open")] = self._on_open
        hds_server.event_handlers[("dataSend", "close")] = self._on_close
        hds_server.event_handlers[("dataSend", "ack")] = self._on_ack

    def _on_open(self, conn, request_id, message):
        stream_id = message.get("streamId")
        if self.prebuffer is None:
            _LOGGER.info("[%s] HKSV: hub asked to record but recording isn't active here", self.name)
            conn.send_response("dataSend", "open", request_id, 6, {"status": 6})
            return
        sess = RecordingSession(self, conn, request_id, stream_id)
        self.sessions.add(sess)
        sess.task = self.loop.create_task(sess.run())

    def _find(self, conn, message):
        sid = message.get("streamId")
        for s in list(self.sessions):
            if s.conn is conn and s.stream_id == sid:
                return s
        return None

    def _on_close(self, conn, message):
        s = self._find(conn, message)
        _LOGGER.debug("[%s] HKSV: hub closed recording stream %s (reason %s)", self.name,
                      message.get("streamId"), message.get("reason"))
        if s:
            s.close()

    def _on_connection_closed(self, conn):
        for s in list(self.sessions):
            if s.conn is conn:
                s.close()

    def _on_ack(self, conn, message):
        s = self._find(conn, message)
        if s:
            s.close()

    def stop(self):
        for s in list(self.sessions):
            s.close()
        if self.prebuffer is not None:
            self.prebuffer.stop()
            self.prebuffer = None
