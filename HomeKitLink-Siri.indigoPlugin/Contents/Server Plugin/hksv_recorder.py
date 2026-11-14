"""HomeKit Secure Video - phase 2: stream check, prebuffer and recording delivery.

Only used for a camera with an HKSV Recorder device.

  * Stream check: each of the camera's streams (BlueIris streams 0-2, UniFi
    High/Medium/Low, SecuritySpy) is probed once with ffprobe in a background
    thread. A stream can be recorded by copying (no re-encoding, almost no CPU)
    when it's H.264, 8-bit 4:2:0, at most 1920x1080 and level 4.2, at most
    30 fps, with a keyframe at least every 4 s. Otherwise the best stream is
    transcoded to the format the hub chose (VideoToolbox by default).
  * Prebuffer: while the Home app allows recording (and the hub has chosen a
    format), one ffmpeg per camera writes fragmented MP4. The init segment and
    the last few seconds are kept in memory, as HomeKit wants recordings to
    start a few seconds before the motion that triggered them. Fragments are
    grouped to the hub's requested fragment length, always starting at a
    keyframe. Audio is always encoded to AAC-LC at the hub's chosen rate.
  * Recording: when the hub sends dataSend/open, the init segment, the
    prebuffer and then live fragments are sent as dataSend/data events in
    chunks of at most 256 KiB, until motion has been clear for one fragment.
    Message layout follows HAP-NodeJS CameraRecordingStream, via PR #42.
  * Usage: the ffmpeg's CPU and memory (ps), output rate and recordings are
    reported to the Recorder device every 30 s.
"""

import asyncio
import collections
import json
import logging
import re
import subprocess
import sys
import time

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn.HKSV")

MAX_CHUNK = 0x40000              # 256 KiB per dataSend packet (HAP-NodeJS)
MAX_RECORDING_SECONDS = 300
MIN_RECORDING_SECONDS = 10       # a doorbell press with little motion still gets a clip
DOORBELL_EXTEND_SECONDS = 30     # a doorbell press keeps a recording going (a visitor standing still)
RESTART_DELAY = 10
USAGE_INTERVAL = 30
PROBE_TIMEOUT = 15
CLOSE_TIMEOUT = 12               # after the last fragment, close if the hub hasn't (HAP-NodeJS)
OPEN_WAIT_SECONDS = 8            # how long an open waits for the prebuffer's init segment and first fragment

# HDS status / protocol-specific reasons (HAP-NodeJS DataStreamServer)
HDS_PROTOCOL_SPECIFIC_ERROR = 6
REASON_NOT_ALLOWED = 1
REASON_BUSY = 2
REASON_CANCELLED = 3
REASON_UNEXPECTED_FAILURE = 5
REASON_INVALID_CONFIGURATION = 9

# Copy limits
COPY_MAX_WIDTH, COPY_MAX_HEIGHT = 1920, 1080
COPY_MAX_LEVEL = 42
COPY_MAX_GOP_SECONDS = 4.0      # typical (median) keyframe gap
COPY_MAX_GOP_PEAK_SECONDS = 8.0 # longest single gap (BlueIris streams vary)
COPY_MAX_FPS = 30.5
BAD_PROFILES = ("High 10", "High 4:2:2", "High 4:4:4 Predictive", "High 10 Intra", "High 4:2:2 Intra")


def _dbg(msg, *args, **kwargs):
    if getattr(sys.modules.get("HKSV"), "DEBUG", False):
        _LOGGER.info("HKSV debug: " + msg, *args, **kwargs)
    else:
        _LOGGER.debug(msg, *args, **kwargs)


def mask(url):
    """UniFi stream URLs carry an access token in the path."""
    return re.sub(r"(rtsps://[^/\s'\",]+/)[^\s:'\",}]+", r"\1****", str(url))


# ------------------------------------------------------------------ sources
def candidate_sources(config):
    """[(label, url)] of the camera's streams worth checking for recording."""
    out = []
    urls = config.get("unifi_urls") or {}
    src = str(config.get("stream_source") or "")
    if urls:
        for key in ("high", "medium", "low"):
            url = urls.get(key)
            if url and url not in [u for _, u in out]:
                out.append(("UniFi " + key.title(), url))
    elif "BI_name" in config and "&stream=" in src:
        base = src.split("&stream=")[0]
        for n in (0, 1, 2):
            out.append(("BlueIris stream {}".format(n), "{}&stream={}".format(base, n)))
    elif "SS_name" in config and src:
        native = re.sub(r"&width=\d+", "", src)
        out.append(("SecuritySpy", native))
        if native != src:
            out.append(("SecuritySpy (resized)", src))
    elif src:
        out.append(("Camera stream", src))
    return out


# -------------------------------------------------------------------- probe
def _rtsp_args(url):
    return ["-rtsp_transport", "tcp"] if str(url).lower().startswith("rtsp") else []


def probe_stream(ffprobe, url, timeout=PROBE_TIMEOUT):
    """Codec, size, level and keyframe interval of one stream."""
    info = {"ok": False}
    try:
        res = subprocess.run([ffprobe, *_rtsp_args(url), "-v", "error",
                              "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate,"
                                               "pix_fmt,profile,level,sample_rate,channels",
                              "-of", "json", "-i", url], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        info["error"] = "no answer in {} s".format(timeout)
        return info
    except Exception as err:  # noqa: BLE001
        info["error"] = str(err)
        return info
    if res.returncode != 0:
        info["error"] = mask((res.stderr or b"").decode(errors="replace").strip().splitlines()[-1:] or ["ffprobe failed"])
        return info
    try:
        streams = json.loads(res.stdout.decode(errors="replace")).get("streams", [])
    except ValueError:
        info["error"] = "unreadable ffprobe output"
        return info
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        info["error"] = "no video"
        return info
    try:
        num, den = str(video.get("r_frame_rate", "0/1")).split("/")
        fps = round(int(num) / int(den), 1) if int(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    info.update(ok=True, codec=video.get("codec_name", "?"), width=int(video.get("width") or 0),
                height=int(video.get("height") or 0), fps=fps, profile=video.get("profile", "?"),
                level=int(video.get("level") or 0), pix_fmt=video.get("pix_fmt", "?"), gop_s=None,
                audio_codec=audio.get("codec_name") if audio else None,
                audio_rate=int(audio.get("sample_rate") or 0) if audio else 0)
    # Keyframe interval from a few seconds of packets (retried once: a short read
    # can catch only one keyframe, and BlueIris leaves the first one's pts unset)
    for _attempt in range(2):
        try:
            res = subprocess.run([ffprobe, *_rtsp_args(url), "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", "packet=pts_time,dts_time,flags", "-of", "csv=p=0",
                                  "-read_intervals", "%+14", "-i", url], capture_output=True, timeout=timeout + 5)
        except subprocess.TimeoutExpired:
            continue
        except Exception:  # noqa: BLE001
            _LOGGER.debug("keyframe probe failed", exc_info=True)
            continue
        times, all_times = [], []
        for line in res.stdout.decode(errors="replace").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            t = None
            for value in parts[:2]:          # pts_time, else dts_time
                try:
                    t = float(value)
                    break
                except ValueError:
                    continue
            if t is None:
                continue
            all_times.append(t)
            if "K" in parts[2]:
                times.append(t)
        # The stream's declared frame rate isn't reliable (BlueIris); measure it
        if len(all_times) > 10 and max(all_times) > min(all_times):
            info["fps"] = round((len(all_times) - 1) / (max(all_times) - min(all_times)), 1)
        if len(times) >= 2:
            gaps = sorted(b - a for a, b in zip(times, times[1:]))
            info["gop_s"] = round(gaps[len(gaps) // 2], 1)      # typical gap
            info["gop_max"] = round(gaps[-1], 1)
            info.pop("gop_long", None)
            break
        if all_times and max(all_times) - min(all_times) > 8:
            info["gop_long"] = True       # fewer than two keyframes in 8+ s of video
    return info


def _gop_text(p):
    if p.get("gop_max") and p["gop_max"] > p["gop_s"]:
        return "{}-{}".format(p["gop_s"], p["gop_max"])
    return str(p["gop_s"])


def copy_check(p):
    """(can copy, reason) for a probed stream."""
    if not p.get("ok"):
        return False, "couldn't read it ({})".format(p.get("error", "?"))
    if p["codec"] != "h264":
        return False, "{} video, not H.264".format(p["codec"])
    if p["pix_fmt"] not in ("yuv420p", "yuvj420p"):
        return False, "pixel format {}".format(p["pix_fmt"])
    if p["profile"] in BAD_PROFILES:
        return False, "H.264 {} profile".format(p["profile"])
    if p["width"] > COPY_MAX_WIDTH or p["height"] > COPY_MAX_HEIGHT:
        return False, "{}x{} is larger than 1920x1080".format(p["width"], p["height"])
    if p["level"] > COPY_MAX_LEVEL:
        return False, "level {:.1f} is above 4.2".format(p["level"] / 10)
    if p["fps"] > COPY_MAX_FPS:
        return False, "{} fps is above 30".format(p["fps"])
    if p["gop_s"] is None:
        return False, ("keyframes more than 8 s apart" if p.get("gop_long")
                       else "keyframe interval couldn't be measured")
    if p["gop_s"] > COPY_MAX_GOP_SECONDS:
        return False, "keyframe every {} s (needs 4 s or less)".format(p["gop_s"])
    if p.get("gop_max", 0) > COPY_MAX_GOP_PEAK_SECONDS:
        return False, "keyframes up to {} s apart (needs 8 s or less)".format(p["gop_max"])
    return True, "H.264 {} {:.1f}, {}x{} @ {} fps, keyframe every {} s".format(
        p["profile"], p["level"] / 10, p["width"], p["height"], p["fps"], _gop_text(p))


def describe_probe(label, p):
    if not p.get("ok"):
        return "{}: unreadable ({})".format(label, p.get("error", "?"))
    ok, why = copy_check(p)
    audio = "{} {} Hz".format(p["audio_codec"], p["audio_rate"]) if p.get("audio_codec") else "no audio"
    return "{}: {} {}x{} @ {} fps, {} {:.1f}, keyframe {} - {}".format(
        label, p["codec"], p["width"], p["height"], p["fps"], p["profile"], p["level"] / 10,
        "every {} s".format(_gop_text(p)) if p["gop_s"] is not None else ("over 8 s" if p.get("gop_long") else "unknown"),
        "copy OK" if ok else "can't copy: " + why) + ", " + audio


def choose_source(sources, probes, selected, allow_copy=True):
    """(index, mode, reason) - the stream to record and whether it can be copied."""
    target_h = (selected or {}).get("video", {}).get("height", 1080) or 1080
    readable = [i for i, p in enumerate(probes) if p.get("ok")]
    if not readable:
        return None, None, "none of the camera's streams could be read"
    copyable = [i for i in readable if copy_check(probes[i])[0]]
    if allow_copy and copyable:
        best = min(copyable, key=lambda i: (abs(probes[i]["height"] - target_h), -probes[i]["height"]))
        return best, "copy", "{} can be copied ({})".format(sources[best][0], copy_check(probes[best])[1])
    # Transcode: the smallest stream at least as tall as the hub asked for, else the tallest
    tall = [i for i in readable if probes[i]["height"] >= target_h]
    best = min(tall, key=lambda i: probes[i]["height"]) if tall else max(readable, key=lambda i: probes[i]["height"])
    if not allow_copy:
        why = "copy is turned off for this Recorder"
    else:
        why = "no stream can be copied ({}: {})".format(sources[best][0], copy_check(probes[best])[1])
    return best, "transcode", "transcoding {} - {}".format(sources[best][0], why)


def build_command(ffmpeg, url, mode, selected, audio_on, encoder="h264_videotoolbox"):
    """ffmpeg command writing fragmented MP4 to stdout."""
    v, a = selected["video"], selected["audio"]
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostats", "-nostdin",
           *_rtsp_args(url), "-fflags", "+genpts+discardcorrupt", "-i", url, "-map", "0:v:0"]
    if audio_on:
        cmd += ["-map", "0:a:0?"]
    if mode == "copy":
        cmd += ["-c:v", "copy"]
    else:
        w, h, fps = v["width"], v["height"], v["fps"] or 30
        iframe_s = max(1.0, (v["iframe_interval_ms"] or 4000) / 1000.0)
        gop = max(1, int(round(fps * iframe_s)))
        kbps = max(300, int(v["bitrate_kbps"] or 2000))
        if encoder == "libx264":
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                    "-keyint_min", str(gop), "-sc_threshold", "0"]
        else:
            cmd += ["-c:v", "h264_videotoolbox", "-realtime", "1", "-allow_sw", "1"]
        cmd += ["-profile:v", v["profile"], "-level:v", v["level"], "-bf", "0",
                "-vf", "scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       "pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1".format(w=w, h=h),
                "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(gop),
                "-force_key_frames", "expr:gte(t,n_forced*{})".format(iframe_s),
                "-b:v", "{}k".format(kbps), "-maxrate", "{}k".format(kbps), "-bufsize", "{}k".format(kbps * 2)]
    if audio_on:
        cmd += ["-c:a", "aac", "-profile:a", "aac_low", "-ar", str(a["sample_rate"]),
                "-ac", str(a["channels"] or 1), "-b:a", "{}k".format(max(16, int(a["bitrate_kbps"] or 64)))]
    else:
        cmd += ["-an"]
    cmd += ["-sn", "-dn", "-f", "mp4", "-movflags", "frag_keyframe+empty_moov+default_base_moof", "pipe:1"]
    return cmd


# --------------------------------------------------------------- prebuffer
class Prebuffer:
    """One ffmpeg writing fMP4; keeps the init segment and recent fragments."""

    def __init__(self, name, loop, cmd, fragment_s, prebuffer_s, on_event=None):
        self.name = name
        self.loop = loop
        self.cmd = cmd
        self.fragment_s = fragment_s
        self.keep_s = prebuffer_s + fragment_s * 2
        self.on_event = on_event or (lambda kind, detail=None: None)
        self.init_segment = None
        self.generation = 0            # bumps on each ffmpeg start; recordings can't span two
        self.groups = collections.deque()   # keyframe fragments: (start, end, generation, bytes)
        self._pending = []
        self._pending_start = None
        self.subscribers = set()
        self.proc = None
        self.task = None
        self.running = False
        self.bytes_out = 0
        self.starts = 0
        self.last_error = ""

    @property
    def pid(self):
        return self.proc.pid if self.proc is not None and self.proc.returncode is None else None

    def start(self):
        if not self.running:
            self.running = True
            self.task = self.loop.create_task(self._run())

    async def stop(self):
        self.running = False
        await self._kill()
        if self.task is not None:
            self.task.cancel()

    async def _kill(self):
        proc = self.proc
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 2)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass

    async def _run(self):
        while self.running:
            err_task = None
            try:
                self.init_segment = None
                self.groups.clear()
                self._pending, self._pending_start = [], None
                self.generation += 1
                self.starts += 1
                _dbg("[%s] prebuffer ffmpeg: %s", self.name, mask(" ".join(self.cmd)))
                self.proc = await asyncio.create_subprocess_exec(
                    *self.cmd, stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                self.on_event("started")
                err_task = self.loop.create_task(self._stderr(self.proc.stderr))
                await self._read_boxes(self.proc.stdout)
            except asyncio.CancelledError:
                break
            except asyncio.IncompleteReadError:
                pass
            except Exception:
                _LOGGER.warning("[%s] HKSV: prebuffer error", self.name, exc_info=True)
            finally:
                await self._kill()
                if err_task is not None:
                    err_task.cancel()
            if self.running:
                self.on_event("stopped", self.last_error)
                _LOGGER.warning("[%s] HKSV: prebuffer ffmpeg stopped%s; restarting in %d s", self.name,
                                " ({})".format(self.last_error) if self.last_error else "", RESTART_DELAY)
                try:
                    await asyncio.sleep(RESTART_DELAY)
                except asyncio.CancelledError:
                    break

    async def _stderr(self, stream):
        while True:
            line = await stream.readline()
            if not line:
                return
            text = mask(line.decode(errors="replace").rstrip())
            if text:
                self.last_error = text[:200]
                _dbg("[%s] prebuffer ffmpeg: %s", self.name, text)

    async def _read_boxes(self, stream):
        init = []
        frag = []
        while True:
            head = await stream.readexactly(8)
            size = int.from_bytes(head[:4], "big")
            btype = head[4:8]
            if size == 1:
                ext = await stream.readexactly(8)
                size = int.from_bytes(ext, "big")
                box = head + ext + await stream.readexactly(size - 16)
            elif size < 8:
                raise ValueError("bad MP4 box size {}".format(size))
            else:
                box = head + await stream.readexactly(size - 8)
            self.bytes_out += len(box)
            if self.init_segment is None and btype in (b"ftyp", b"moov"):
                init.append(box)
                if btype == b"moov":
                    self.init_segment = b"".join(init)
                    _dbg("[%s] prebuffer: init segment %d bytes", self.name, len(self.init_segment))
            elif btype == b"mdat" and frag:
                frag.append(box)
                self._add_fragment(b"".join(frag))
                frag = []
            elif btype == b"moof":
                frag = [box]
            elif frag:
                frag.append(box)

    def _add_fragment(self, data):
        """Keep each keyframe fragment for the prebuffer, and group live ones up to
        the hub's fragment length for recordings in progress."""
        now = time.monotonic()
        last_end = self.groups[-1][1] if self.groups else None
        # A fragment ends when the next keyframe arrives; the first one's length isn't known
        start = last_end if last_end is not None else now - self.fragment_s
        frag = (start, now, self.generation, data)
        self.groups.append(frag)
        while self.groups and self.groups[0][1] < now - self.keep_s:
            self.groups.popleft()
        if self._pending_start is None:
            self._pending_start = start
        self._pending.append(data)
        if now - self._pending_start >= self.fragment_s * 0.9 or sum(map(len, self._pending)) > 8 << 20:
            group = (self._pending_start, now, self.generation, b"".join(self._pending))
            self._pending, self._pending_start = [], None
            for q in list(self.subscribers):
                q.put_nowait(group)

    def prebuffered(self, seconds):
        """The newest fragments covering at least `seconds`, as one group. Live groups
        then start after them, so nothing is sent twice."""
        picked, total = [], 0.0
        for frag in reversed(self.groups):
            picked.insert(0, frag)
            total += frag[1] - frag[0]
            if total >= seconds:
                break
        self._pending, self._pending_start = [], None
        if not picked:
            return None
        return (picked[0][0], picked[-1][1], picked[-1][2], b"".join(f[3] for f in picked))

    def buffered_seconds(self):
        if not self.groups:
            return 0.0
        return round(min(self.keep_s, time.monotonic() - self.groups[0][0]), 1)

    def subscribe(self):
        q = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        self.subscribers.discard(q)


# ------------------------------------------------------------------ session
class RecordingSession:
    """One dataSend stream to one hub."""

    def __init__(self, recorder, conn, request_id, stream_id):
        self.r = recorder
        self.conn = conn
        self.request_id = request_id
        self.stream_id = stream_id
        self.closed = False
        self.task = None
        self.bytes_sent = 0
        self.started = time.time()

    def close(self):
        self.closed = True
        if self.task is not None:
            self.task.cancel()

    async def _send(self, data, initialization, seq, is_last):
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
            await self.conn.drain()
            self.bytes_sent += len(part)
            chunk_seq += 1

    def _close_event(self, reason):
        try:
            self.conn.send_event("dataSend", "close", {"streamId": self.stream_id, "reason": reason})
        except Exception:  # noqa: BLE001
            pass

    async def run(self):
        r = self.r
        name = r.name
        started = time.monotonic()
        sent = 0
        q = None
        try:
            # Wait for the init segment and at least one keyframe fragment (with keyframes
            # several seconds apart, the first one can take a while after a restart)
            for _ in range(OPEN_WAIT_SECONDS * 10):
                if r.prebuffer is not None and r.prebuffer.init_segment and r.prebuffer.groups:
                    break
                await asyncio.sleep(0.1)
            pb = r.prebuffer
            if pb is None or not pb.init_segment:
                _LOGGER.warning("[%s] HKSV: the hub asked to record but the prebuffer has no video yet", name)
                r.open_error(self.conn, self.request_id, REASON_UNEXPECTED_FAILURE)
                return
            generation = pb.generation
            q = pb.subscribe()
            self.conn.send_response("dataSend", "open", self.request_id, 0, {"status": 0})
            await self.conn.drain()
            seq = 1
            await self._send(pb.init_segment, True, seq, False)
            held = len(pb.groups)
            pre = pb.prebuffered(r.prebuffer_s)
            _dbg("[%s] recording open: %d keyframe fragments held (%.1f s), sending %s", name, held,
                 pb.buffered_seconds(), "{:.1f} s".format(pre[1] - pre[0]) if pre else "none")
            if pre is not None:
                seq += 1
                await self._send(pre[3], False, seq, False)
                sent += 1
            _LOGGER.info("[%s] HKSV: recording to hub %s (%.1f s of prebuffer)", name,
                         self.conn.peer[0] if self.conn.peer else "?", (pre[1] - pre[0]) if pre else 0.0)
            r.recording_started(self)
            clear_since = None
            last = False
            while not self.closed and not last:
                group = await asyncio.wait_for(q.get(), timeout=r.fragment_s * 3 + 10)
                if group[2] != generation:
                    _LOGGER.warning("[%s] HKSV: the camera stream restarted during a recording - ending it", name)
                    self._close_event(REASON_UNEXPECTED_FAILURE)
                    return
                now = time.monotonic()
                if r.activity():
                    clear_since = None
                elif clear_since is None:
                    clear_since = now
                last = (now - started > MAX_RECORDING_SECONDS or
                        (clear_since is not None and now - clear_since >= r.fragment_s
                         and now - started >= MIN_RECORDING_SECONDS))
                seq += 1
                await self._send(group[3], False, seq, last)
                sent += 1
            if last:
                _LOGGER.info("[%s] HKSV: recording finished - %.0f s, %.1f MB", name,
                             time.monotonic() - started, self.bytes_sent / 1e6)
                # The hub closes the stream; if it doesn't, close it ourselves (as HAP-NodeJS)
                for _ in range(CLOSE_TIMEOUT * 10):
                    if self.closed:
                        break
                    await asyncio.sleep(0.1)
                else:
                    self._close_event(REASON_CANCELLED)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            _LOGGER.warning("[%s] HKSV: no video from the prebuffer - ending the recording", name)
            self._close_event(REASON_UNEXPECTED_FAILURE)
        except (ConnectionError, OSError):
            _dbg("[%s] HKSV: the hub's data stream closed during a recording", name)
        except Exception:
            _LOGGER.warning("[%s] HKSV: recording stream error", name, exc_info=True)
            self._close_event(REASON_UNEXPECTED_FAILURE)
        finally:
            if q is not None and r.prebuffer is not None:
                r.prebuffer.unsubscribe(q)
            r.recording_ended(self, time.monotonic() - started)


# ----------------------------------------------------------------- recorder
class Recorder:
    """Stream check, prebuffer, recordings and usage for one HKSV camera."""

    def __init__(self, name, loop, config, motion_getter, on_change, allow_copy=True,
                 encoder="h264_videotoolbox"):
        self.name = name
        self.loop = loop
        self.config = config
        self.motion_active = motion_getter
        self.on_change = on_change
        self.allow_copy = allow_copy
        self.encoder = encoder
        try:
            from homekitlink_ffmpeg import get_ffmpeg_binary, get_ffprobe_binary
            self.ffmpeg, self.ffprobe = get_ffmpeg_binary(), get_ffprobe_binary()
        except Exception:  # noqa: BLE001
            self.ffmpeg, self.ffprobe = "ffmpeg", "ffprobe"
        self.sources = candidate_sources(config)
        self.probes = None             # None until the stream check has finished
        self.choice = (None, None, "")
        self.prebuffer = None
        self.wanted = None             # (selected, audio_on) while recording is allowed
        self.running_key = None
        self.prebuffer_s = 4.0
        self.fragment_s = 4.0
        self.session = None
        self.recordings_today = 0
        self._today = time.strftime("%Y-%m-%d")
        self.last_recording = {}
        self.cpu = 0.0
        self.mem_mb = 0.0
        self.kbps = 0
        self._last_bytes = (time.monotonic(), 0)
        self.last_error = ""
        self._usage_task = None
        self._closed = False
        self.doorbell_extends = True
        self.last_doorbell = 0.0

    def doorbell_pressed(self):
        self.last_doorbell = time.monotonic()
        _dbg("[%s] doorbell pressed", self.name)

    def activity(self):
        """Motion, or (if set) a doorbell press in the last 30 s, keeps a recording going."""
        if self.motion_active():
            return True
        return self.doorbell_extends and time.monotonic() - self.last_doorbell < DOORBELL_EXTEND_SECONDS

    # ---------------------------------------------------------- stream check
    def start_probe(self):
        import threading
        threading.Thread(target=self._probe_thread, daemon=True, name="HKLS-hksv-probe").start()

    def _probe_thread(self):
        if not self.sources:
            results = []
        else:
            results = [probe_stream(self.ffprobe, url) for _, url in self.sources]
        try:
            self.loop.call_soon_threadsafe(self._probed, results)
        except RuntimeError:
            pass   # bridge already stopped

    def _probed(self, results):
        if self._closed:
            return
        self.probes = results
        for (label, _), p in zip(self.sources, results):
            _LOGGER.info("[%s] HKSV stream check - %s", self.name, describe_probe(label, p))
        if not self.sources:
            _LOGGER.warning("[%s] HKSV: no stream URL found for this camera", self.name)
        self._apply()

    def summary(self):
        if self.probes is None:
            return "Checking streams" if self.sources else "No stream found"
        parts = []
        for (label, _), p in zip(self.sources, self.probes):
            if not p.get("ok"):
                parts.append("{}: unreadable".format(label))
            else:
                parts.append("{}: {}x{} {}".format(label, p["width"], p["height"],
                                                   "copy" if copy_check(p)[0] else "no copy"))
        return "; ".join(parts)

    # -------------------------------------------------------------- control
    def configure(self, selected, enabled, audio_on):
        """Called on the bridge loop when anything the prebuffer depends on changes."""
        self.wanted = (selected, bool(audio_on)) if (enabled and selected) else None
        self._apply()

    def set_options(self, allow_copy, encoder):
        self.allow_copy, self.encoder = bool(allow_copy), encoder or "h264_videotoolbox"
        self._apply()

    def _apply(self):
        if self._closed:
            return
        if self.wanted is None or self.probes is None:
            if self.prebuffer is not None:
                self._stop_prebuffer("recording not allowed" if self.wanted is None else "")
            self.on_change()
            return
        selected, audio_on = self.wanted
        idx, mode, reason = choose_source(self.sources, self.probes, selected, self.allow_copy)
        self.choice = (idx, mode, reason)
        if idx is None:
            self.last_error = reason
            if self.prebuffer is not None:
                self._stop_prebuffer(reason)
            _LOGGER.warning("[%s] HKSV: can't record - %s", self.name, reason)
            self.on_change()
            return
        key = (idx, mode, audio_on, self.encoder, repr(selected))
        if self.prebuffer is not None and key == self.running_key:
            return
        if self.prebuffer is not None:
            self._stop_prebuffer("settings changed")
        self.prebuffer_s = max(1.0, (selected.get("prebuffer_ms") or 4000) / 1000.0)
        self.fragment_s = max(1.0, (selected.get("fragment_ms") or 4000) / 1000.0)
        cmd = build_command(self.ffmpeg, self.sources[idx][1], mode, selected, audio_on, self.encoder)
        self.prebuffer = Prebuffer(self.name, self.loop, cmd, self.fragment_s, self.prebuffer_s, self._pb_event)
        self.running_key = key
        self.prebuffer.start()
        v = selected["video"]
        _LOGGER.info("[%s] HKSV: prebuffer started - %s%s", self.name, reason,
                     "" if mode == "copy" else " to {}x{}@{} {} kbps ({})".format(
                         v["width"], v["height"], v["fps"], v["bitrate_kbps"],
                         "VideoToolbox" if self.encoder != "libx264" else "libx264"))
        if self._usage_task is None:
            self._usage_task = self.loop.create_task(self._usage_loop())
        self.on_change()

    def _stop_prebuffer(self, why):
        pb, self.prebuffer, self.running_key = self.prebuffer, None, None
        if self.session is not None:
            self.session.close()
        if pb is not None:
            self.loop.create_task(pb.stop())
            if why:
                _LOGGER.info("[%s] HKSV: prebuffer stopped (%s)", self.name, why)
        self.cpu = self.mem_mb = 0.0
        self.kbps = 0

    def _pb_event(self, kind, detail=None):
        if kind == "stopped":
            self.last_error = detail or "ffmpeg stopped"
        self.on_change()

    def close(self):
        self._closed = True
        if self._usage_task is not None:
            self._usage_task.cancel()
            self._usage_task = None
        self._stop_prebuffer("")

    # ---------------------------------------------------------------- usage
    async def _usage_loop(self):
        try:
            while not self._closed:
                await asyncio.sleep(USAGE_INTERVAL)
                pb = self.prebuffer
                pid = pb.pid if pb is not None else None
                if pid:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "/bin/ps", "-o", "%cpu=,rss=", "-p", str(pid),
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                        out, _ = await proc.communicate()
                        cpu, rss = out.decode().split()[:2]
                        self.cpu, self.mem_mb = round(float(cpu), 1), round(int(rss) / 1024, 1)
                    except Exception:  # noqa: BLE001
                        pass
                    now = time.monotonic()
                    t0, b0 = self._last_bytes
                    self.kbps = int((pb.bytes_out - b0) * 8 / 1000 / max(1.0, now - t0)) if pb.bytes_out >= b0 else 0
                    self._last_bytes = (now, pb.bytes_out)
                else:
                    self.cpu = self.mem_mb = 0.0
                    self.kbps = 0
                self.on_change()
        except asyncio.CancelledError:
            pass

    def states(self):
        idx, mode, reason = self.choice
        if time.strftime("%Y-%m-%d") != self._today:
            self._today, self.recordings_today = time.strftime("%Y-%m-%d"), 0
        pb = self.prebuffer
        return {
            "streamCheck": self.summary(),
            "recordSource": self.sources[idx][0] if idx is not None and self.prebuffer is not None else "",
            "recordMode": mode if self.prebuffer is not None else "",
            "recordModeReason": reason if self.prebuffer is not None else "",
            "ffmpegCpuPercent": self.cpu,
            "ffmpegMemoryMB": self.mem_mb,
            "prebufferKbps": self.kbps,
            "prebufferSeconds": pb.buffered_seconds() if pb is not None else 0.0,
            "ffmpegRestarts": max(0, pb.starts - 1) if pb is not None else 0,
            "recordingsToday": self.recordings_today,
            "lastRecordingStart": self.last_recording.get("start", ""),
            "lastRecordingSeconds": self.last_recording.get("seconds", 0),
            "lastRecordingMB": self.last_recording.get("mb", 0.0),
            "lastError": self.last_error,
        }

    def buffering(self):
        return self.prebuffer is not None and self.prebuffer.init_segment is not None

    # ------------------------------------------------------- data stream
    def attach(self, hds_server):
        hds_server.on_connection_closed = self._on_connection_closed
        hds_server.request_handlers[("dataSend", "open")] = self._on_open
        hds_server.event_handlers[("dataSend", "close")] = self._on_close
        hds_server.event_handlers[("dataSend", "ack")] = self._on_ack

    def open_error(self, conn, request_id, reason):
        try:
            conn.send_response("dataSend", "open", request_id, HDS_PROTOCOL_SPECIFIC_ERROR, {"status": reason})
        except Exception:  # noqa: BLE001
            pass

    def _on_open(self, conn, request_id, message):
        stream_id = message.get("streamId")
        _dbg("[%s] hub %s: dataSend/open %s", self.name, conn.peer[0] if conn.peer else "?",
             {k: v for k, v in message.items()})
        if message.get("target") != "controller" or message.get("type") != "ipcamera.recording":
            self.open_error(conn, request_id, REASON_UNEXPECTED_FAILURE)
            return
        if self.wanted is None:
            _LOGGER.info("[%s] HKSV: the hub asked to record but recording isn't allowed right now", self.name)
            self.open_error(conn, request_id, REASON_NOT_ALLOWED)
            return
        if self.prebuffer is None:
            self.open_error(conn, request_id, REASON_INVALID_CONFIGURATION if self.probes is not None
                            else REASON_UNEXPECTED_FAILURE)
            return
        if self.session is not None:
            self.open_error(conn, request_id, REASON_BUSY)
            return
        sess = RecordingSession(self, conn, request_id, stream_id)
        self.session = sess
        sess.task = self.loop.create_task(sess.run())

    def _match(self, conn, message):
        s = self.session
        return s if s is not None and s.conn is conn and s.stream_id == message.get("streamId") else None

    def _on_close(self, conn, message):
        _dbg("[%s] hub closed recording stream %s (reason %s)", self.name, message.get("streamId"),
             message.get("reason"))
        s = self._match(conn, message)
        if s:
            s.close()

    def _on_ack(self, conn, message):
        _dbg("[%s] hub acknowledged recording stream %s", self.name, message.get("streamId"))
        s = self._match(conn, message)
        if s:
            s.close()

    def _on_connection_closed(self, conn):
        if self.session is not None and self.session.conn is conn:
            self.session.close()

    def recording_started(self, sess):
        self.last_recording = {"start": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sess.started)),
                               "seconds": 0, "mb": 0.0}
        self.on_change(recording=True)

    def recording_ended(self, sess, seconds):
        if self.session is sess:
            self.session = None
        if self.last_recording.get("start") and sess.bytes_sent:
            self.recordings_today += 1
            self.last_recording.update(seconds=int(seconds), mb=round(sess.bytes_sent / 1e6, 1))
        self.on_change(recording=False)
