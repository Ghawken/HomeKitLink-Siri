"""HomeKit Secure Video (HKSV) support for HomeKitLink cameras.

Stage 1: advertise the recording services and handle the home hub's
configuration. Modelled on HAP-NodeJS lib/camera/RecordingManagement.js
(TLV layouts, list delimiters and defaults follow it exactly).

Services added to the camera accessory:
  * CameraOperatingMode            (HomeKitCameraActive, EventSnapshotsActive, PeriodicSnapshotsActive)
  * CameraRecordingManagement      (Active, Supported*/SelectedCameraRecordingConfiguration, RecordingAudioActive)
  * DataStreamTransportManagement  (SetupDataStreamTransport, SupportedDataStreamTransportConfiguration, Version)
plus an Active characteristic on each CameraRTPStreamManagement service.

State (selected configuration and the Home app's recording switches) is
persisted per camera, as HAP-NodeJS does, so it survives restarts.
"""

import base64
import hashlib
import json
import logging
import os
import struct

from pyhap import tlv

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn.HKSV")

# --- TLV type ids (HAP-NodeJS RecordingManagement.js) ---
SUPPORTED_CAMERA_PREBUFFER_LENGTH = b"\x01"
SUPPORTED_CAMERA_EVENT_TRIGGER_OPTIONS = b"\x02"
SUPPORTED_CAMERA_MEDIA_CONTAINER_CONFIGURATIONS = b"\x03"
MEDIA_CONTAINER_TYPE = b"\x01"
MEDIA_CONTAINER_PARAMETERS = b"\x02"
MEDIA_CONTAINER_FRAGMENT_LENGTH = b"\x01"

SUPPORTED_VIDEO_CODEC_CONFIGURATION = b"\x01"
VIDEO_CODEC_TYPE = b"\x01"
VIDEO_CODEC_PARAMETERS = b"\x02"
VIDEO_ATTRIBUTES = b"\x03"
VIDEO_PARAM_PROFILE_ID = b"\x01"
VIDEO_PARAM_LEVEL = b"\x02"
VIDEO_PARAM_BITRATE = b"\x03"
VIDEO_PARAM_IFRAME_INTERVAL = b"\x04"
VIDEO_ATTR_WIDTH = b"\x01"
VIDEO_ATTR_HEIGHT = b"\x02"
VIDEO_ATTR_FPS = b"\x03"

SUPPORTED_AUDIO_CODEC_CONFIGURATION = b"\x01"
AUDIO_CODEC_TYPE = b"\x01"
AUDIO_CODEC_PARAMETERS = b"\x02"
AUDIO_PARAM_CHANNEL = b"\x01"
AUDIO_PARAM_BIT_RATE = b"\x02"
AUDIO_PARAM_SAMPLE_RATE = b"\x03"
AUDIO_PARAM_MAX_BITRATE = b"\x04"

SELECTED_RECORDING = 1
SELECTED_VIDEO = 2
SELECTED_AUDIO = 3

EVENT_TRIGGER_MOTION = 0x01
EVENT_TRIGGER_DOORBELL = 0x02

AUDIO_AAC_LC = 0
AUDIO_AAC_ELD = 1
SAMPLE_RATES = {0: 8000, 1: 16000, 2: 24000, 3: 32000, 4: 44100, 5: 48000}
H264_PROFILES = {0: "baseline", 1: "main", 2: "high"}
H264_LEVELS = {0: "3.1", 1: "3.2", 2: "4.0"}

# DataStreamTransportManagement
DS_TRANSFER_TRANSPORT_CONFIGURATION = b"\x01"
DS_TRANSPORT_TYPE = b"\x01"
DS_TRANSPORT_TCP = b"\x00"
DS_SETUP_COMMAND_TYPE = 1
DS_SETUP_TRANSPORT_TYPE = 2
DS_SETUP_CONTROLLER_KEY_SALT = 3
DS_RESPONSE_STATUS = b"\x01"
DS_STATUS_SUCCESS = b"\x00"
DS_STATUS_GENERIC_ERROR = b"\x01"
DS_STATUS_BUSY = b"\x02"

TLV_DELIMITER = b"\x00\x00"

PREBUFFER_MS = 4000
FRAGMENT_MS = 4000


def _tlv_list(type_byte, values):
    """Encode a TLV list the HAP-NodeJS way: entries of the same type
    separated by an empty 0x00 TLV."""
    return TLV_DELIMITER.join(tlv.encode(type_byte, v) for v in values)


def _decode(data):
    """Decode a TLV8 blob into {type_int: bytes}, joining split entries."""
    out, i = {}, 0
    last_type, last_len = None, None
    while i + 2 <= len(data):
        t, ln = data[i], data[i + 1]
        val = data[i + 2:i + 2 + ln]
        i += 2 + ln
        if t == 0:
            last_type, last_len = None, None
            continue
        if t in out and last_type == t and last_len == 255:
            out[t] += val
        elif t not in out:
            out[t] = val
        last_type, last_len = t, ln
    return out


def _u32(b):
    return struct.unpack("<I", (b + b"\x00" * 4)[:4])[0]


def _u16(b):
    return struct.unpack("<H", (b + b"\x00" * 2)[:2])[0]


class HKSVRecording:
    """Adds and manages the HKSV services on one camera accessory."""

    def __init__(self, accessory, config, storage_dir, motion_service=None, doorbell=False, doorbell_service=None):
        self.acc = accessory
        self.name = accessory.display_name
        self.storage_path = os.path.join(storage_dir, "hksv-{}.json".format(accessory.aid)) if storage_dir else None
        self.selected = None          # parsed selected configuration
        self.selected_b64 = ""
        self.recording_active = False
        self.motion_service = motion_service
        self.doorbell_service = doorbell_service

        resolutions = config.get("hksv_resolutions") or [(1920, 1080), (1280, 720), (640, 360)]
        self._supported_camera = self._supported_camera_config(doorbell)
        self._supported_video = self._supported_video_config(resolutions)
        self._supported_audio = self._supported_audio_config()
        self._config_hash = hashlib.sha256(
            (self._supported_camera + self._supported_video + self._supported_audio).encode()).hexdigest()

        self._build_services()
        self.recorder = None
        try:
            from hksv_recorder import Recorder
            motion_char = getattr(accessory, "char_motion_detected", None)
            plugin = getattr(accessory, "plugin", None)
            self.last_doorbell_press = 0.0

            def activity():
                # Motion keeps a recording going; optionally a recent doorbell
                # press does too (a visitor standing still at the door).
                if motion_char is not None and motion_char.value:
                    return True
                if getattr(plugin, "hksv_doorbell_extends", True) and self.last_doorbell_press:
                    import time as _t
                    return _t.monotonic() - self.last_doorbell_press < 30
                return False
            self.recorder = Recorder(
                self.name, config.get("hksv_ffmpeg"), config.get("stream_source"), accessory.driver.loop,
                activity, hw_getter=lambda: getattr(plugin, "use_hw_encoding", False))
        except Exception:
            _LOGGER.warning("[%s] HKSV: recorder unavailable", self.name, exc_info=True)
        self._restore()
        self._update_recorder()

    # ------------------------------------------------------------------ TLVs
    @staticmethod
    def _supported_camera_config(doorbell):
        triggers = EVENT_TRIGGER_MOTION | (EVENT_TRIGGER_DOORBELL if doorbell else 0)
        container = tlv.encode(
            MEDIA_CONTAINER_TYPE, b"\x00",  # fragmented MP4
            MEDIA_CONTAINER_PARAMETERS, tlv.encode(MEDIA_CONTAINER_FRAGMENT_LENGTH, struct.pack("<i", FRAGMENT_MS)))
        return tlv.encode(
            SUPPORTED_CAMERA_PREBUFFER_LENGTH, struct.pack("<i", PREBUFFER_MS),
            SUPPORTED_CAMERA_EVENT_TRIGGER_OPTIONS, struct.pack("<q", triggers),
            SUPPORTED_CAMERA_MEDIA_CONTAINER_CONFIGURATIONS, container,
            to_base64=True)

    @staticmethod
    def _supported_video_config(resolutions):
        params = (_tlv_list(VIDEO_PARAM_PROFILE_ID, [b"\x00", b"\x01", b"\x02"]) +
                  _tlv_list(VIDEO_PARAM_LEVEL, [b"\x00", b"\x01", b"\x02"]))
        attrs = []
        for (w, h) in resolutions:
            for fps in (30, 15):
                attrs.append(tlv.encode(VIDEO_ATTR_WIDTH, struct.pack("<H", w),
                                        VIDEO_ATTR_HEIGHT, struct.pack("<H", h),
                                        VIDEO_ATTR_FPS, struct.pack("<B", fps)))
        codec = (tlv.encode(VIDEO_CODEC_TYPE, b"\x00", VIDEO_CODEC_PARAMETERS, params) +
                 _tlv_list(VIDEO_ATTRIBUTES, attrs))
        return tlv.encode(SUPPORTED_VIDEO_CODEC_CONFIGURATION, codec, to_base64=True)

    @staticmethod
    def _supported_audio_config():
        # AAC-LC, mono, variable bitrate, 32/44.1/48 kHz (as homebridge-unifi-protect)
        params = (tlv.encode(AUDIO_PARAM_CHANNEL, b"\x01", AUDIO_PARAM_BIT_RATE, b"\x00") +
                  _tlv_list(AUDIO_PARAM_SAMPLE_RATE, [b"\x03", b"\x04", b"\x05"]))
        codec = tlv.encode(AUDIO_CODEC_TYPE, bytes([AUDIO_AAC_LC]), AUDIO_CODEC_PARAMETERS, params)
        return tlv.encode(SUPPORTED_AUDIO_CODEC_CONFIGURATION, codec, to_base64=True)

    @staticmethod
    def parse_selected(value_b64):
        decoded = _decode(base64.b64decode(value_b64))
        rec = _decode(decoded[SELECTED_RECORDING])
        video = _decode(decoded[SELECTED_VIDEO])
        audio = _decode(decoded[SELECTED_AUDIO])
        container = _decode(rec[3])
        container_params = _decode(container[2])
        vparams = _decode(video[2])
        vattrs = _decode(video[3])
        aparams = _decode(audio[2])
        return {
            "prebuffer_ms": _u32(rec[1]),
            "event_triggers": _u32(rec[2]),
            "fragment_ms": _u32(container_params[1]),
            "video": {
                "profile": H264_PROFILES.get(vparams[1][0], "high"),
                "level": H264_LEVELS.get(vparams[2][0], "4.0"),
                "bitrate_kbps": _u32(vparams[3]),
                "iframe_interval_ms": _u32(vparams[4]),
                "width": _u16(vattrs[1]),
                "height": _u16(vattrs[2]),
                "fps": vattrs[3][0],
            },
            "audio": {
                "codec": "aac-eld" if audio[1][0] == AUDIO_AAC_ELD else "aac-lc",
                "channels": aparams[1][0],
                "bitrate_mode": "constant" if aparams[2][0] else "variable",
                "sample_rate": SAMPLE_RATES.get(aparams[3][0], 48000),
                "bitrate_kbps": _u32(aparams.get(4, b"")),
            },
        }

    # -------------------------------------------------------------- services
    def _build_services(self):
        acc = self.acc
        loader = acc.driver.loader

        # Active on each RTP stream management service (required for HKSV cameras)
        self._rtp_active = []
        for mgmt in getattr(acc, "_management", []):
            char = loader.get_char("Active")
            char.set_value(1)
            char.setter_callback = self._on_streaming_active
            self._attach(mgmt, char)
            self._rtp_active.append(char)

        om = acc.add_preload_service("CameraOperatingMode", chars=["PeriodicSnapshotsActive"])
        self.char_camera_active = om.configure_char("HomeKitCameraActive", value=1, setter_callback=self._on_camera_active)
        self.char_event_snapshots = om.configure_char("EventSnapshotsActive", value=1, setter_callback=self._on_simple("EventSnapshotsActive"))
        self.char_periodic_snapshots = om.configure_char("PeriodicSnapshotsActive", value=1, setter_callback=self._on_simple("PeriodicSnapshotsActive"))

        ds = acc.add_preload_service("DataStreamTransportManagement")
        ds.configure_char("SupportedDataStreamTransportConfiguration",
                          value=tlv.encode(DS_TRANSFER_TRANSPORT_CONFIGURATION,
                                           tlv.encode(DS_TRANSPORT_TYPE, DS_TRANSPORT_TCP), to_base64=True))
        ds.configure_char("Version", value="1.0")
        self.char_setup_ds = ds.configure_char("SetupDataStreamTransport", value="", setter_callback=self._on_setup_data_stream)
        self._ds_client = None
        self.hds = None
        self.ds_service = ds

        rm = acc.add_preload_service("CameraRecordingManagement", chars=["RecordingAudioActive"])
        self._reads_logged = set()
        for cname, val in (("SupportedCameraRecordingConfiguration", self._supported_camera),
                           ("SupportedVideoRecordingConfiguration", self._supported_video),
                           ("SupportedAudioRecordingConfiguration", self._supported_audio)):
            rm.configure_char(cname, value=val, getter_callback=self._read_logger(cname, val))
        self.char_selected = rm.configure_char("SelectedCameraRecordingConfiguration", value="",
                                               setter_callback=self._on_selected_configuration,
                                               getter_callback=self._read_selected)
        self.char_recording_active = rm.configure_char("Active", value=0, setter_callback=self._on_recording_active)
        self.char_recording_audio = rm.configure_char("RecordingAudioActive", value=0,
                                                      setter_callback=self._on_simple("RecordingAudioActive"))
        # As HAP-NodeJS: recording management is linked to the data stream
        # service AND the motion sensor that triggers recordings, and a video
        # doorbell's Doorbell service is the accessory's primary service.
        rm.add_linked_service(ds)
        self.rm_service = rm

        # Motion sensor reports StatusActive mirroring HomeKitCameraActive
        self.char_status_active = None
        if self.motion_service is not None:
            try:
                self.char_status_active = self.motion_service.configure_char("StatusActive", value=True)
            except Exception:
                try:
                    char = loader.get_char("StatusActive")
                    char.set_value(True)
                    self._attach(self.motion_service, char)
                    self.char_status_active = char
                except Exception:
                    _LOGGER.debug("[%s] HKSV: couldn't add StatusActive to motion sensor", self.name, exc_info=True)

        _LOGGER.info("[%s] HomeKit Secure Video services added", self.name)

    def _attach(self, service, char):
        """Add a characteristic to a service that's already on the accessory,
        giving it a broker and a stable IID like add_service would."""
        service.add_characteristic(char)
        if service.broker is not None:
            char.broker = service.broker
            service.broker.iid_manager.assign(char)

    # ---------------------------------------------------------------- reads
    def _read_logger(self, cname, value):
        def getter():
            if cname not in self._reads_logged:
                self._reads_logged.add(cname)
                _LOGGER.info("[%s] HKSV: hub read %s", self.name, cname)
            return value
        return getter

    def _read_selected(self):
        # 0.8.07.14-15 returned an error here (as HAP-NodeJS does) and the
        # accessory listing then left the value out. HKSV cameras were only
        # ever accepted by HomeKit with 0.8.07.13's behaviour - an empty value -
        # so that's restored.
        if not self.selected_b64 and "selected-none" not in self._reads_logged:
            self._reads_logged.add("selected-none")
            _LOGGER.debug("[%s] HKSV: selected recording configuration read - none chosen yet", self.name)
        return self.selected_b64 or ""

    # -------------------------------------------------------------- setters
    # The Home app re-writes these switches often; only log real changes.
    def _changed(self, key, value):
        last = getattr(self, "_last_values", {})
        self._last_values = last
        if last.get(key) == value:
            return False
        last[key] = value
        return True

    def _on_simple(self, label):
        def setter(value):
            if self._changed(label, value):
                _LOGGER.info("[%s] HKSV: %s set to %s", self.name, label, value)
                self._persist()
        return setter

    def _on_streaming_active(self, value):
        if self._changed("streaming", value):
            _LOGGER.info("[%s] HKSV: live streaming %s", self.name, "allowed" if value else "turned off in the Home app")
            self._persist()

    def _update_recorder(self):
        """Run the prebuffer only while the hub has recording enabled."""
        if self.recorder is None:
            return
        enabled = bool(self.recording_active and self.selected and (self.char_camera_active.value or 0))
        try:
            self.recorder.configure(self.selected, enabled)
        except Exception:
            _LOGGER.debug("[%s] HKSV: recorder configure failed", self.name, exc_info=True)

    def _on_camera_active(self, value):
        if self.char_status_active is not None:
            self.char_status_active.set_value(bool(value))
        self._update_recorder()
        if self._changed("camera", value):
            _LOGGER.info("[%s] HKSV: camera %s in the Home app", self.name, "on" if value else "off")
            self._persist()

    def _on_recording_active(self, value):
        self.recording_active = bool(value)
        self._update_recorder()
        if self._changed("recording", value):
            _LOGGER.info("[%s] HKSV: recording %s%s", self.name, "enabled" if value else "disabled",
                         "" if (not value or self.selected) else " (no recording configuration selected yet)")
            self._persist()

    def _on_selected_configuration(self, value):
        try:
            parsed = self.parse_selected(value)
        except Exception:
            _LOGGER.warning("[%s] HKSV: couldn't parse the selected recording configuration", self.name)
            _LOGGER.debug("raw value %r", value, exc_info=True)
            return
        changed = value != self.selected_b64
        self.selected_b64 = value
        self.selected = parsed
        self._update_recorder()
        if changed:
            v, a = parsed["video"], parsed["audio"]
            _LOGGER.info("[%s] HKSV: hub selected %dx%d@%dfps H.264 %s %s, %d kbps, keyframe every %d ms; "
                         "%s %d Hz %d kbps; prebuffer %d ms, fragments %d ms, triggers=%s",
                         self.name, v["width"], v["height"], v["fps"], v["profile"], v["level"],
                         v["bitrate_kbps"], v["iframe_interval_ms"], a["codec"], a["sample_rate"],
                         a["bitrate_kbps"], parsed["prebuffer_ms"], parsed["fragment_ms"],
                         "+".join(n for b, n in ((1, "motion"), (2, "doorbell")) if parsed["event_triggers"] & b) or "none")
            self._persist()

    def _on_setup_data_stream(self, value):
        """Stage 2: prepare a HomeKit Data Stream session for the hub."""
        failure = tlv.encode(DS_RESPONSE_STATUS, DS_STATUS_GENERIC_ERROR, to_base64=True)
        try:
            req = _decode(base64.b64decode(value))
            cmd = req.get(DS_SETUP_COMMAND_TYPE, b"\xff")[0]
            transport = req.get(DS_SETUP_TRANSPORT_TYPE, b"\xff")[0]
            controller_salt = req.get(DS_SETUP_CONTROLLER_KEY_SALT, b"")
        except Exception:
            _LOGGER.debug("[%s] HKSV: bad SetupDataStreamTransport %r", self.name, value, exc_info=True)
            return failure
        if cmd != 0 or transport != 0 or len(controller_salt) != 32:
            _LOGGER.warning("[%s] HKSV: unsupported data stream request (command %d, transport %d, salt %d bytes)",
                            self.name, cmd, transport, len(controller_salt))
            return failure
        shared = None
        try:
            # Which HAP connection wrote this? Its session secret keys the stream.
            from pyhap import accessory_driver as _ad
            self._ds_client = _ad.CURRENT_WRITE_CLIENT
            conns = self.acc.driver.http_server.connections
            proto = conns.get(self._ds_client)
            shared = getattr(proto, "hds_shared_secret", None)
        except Exception:
            pass
        if not shared:
            _LOGGER.warning("[%s] HKSV: data stream requested by %s but its HAP session secret isn't available",
                            self.name, self._ds_client)
            return failure
        try:
            if self.hds is None:
                from hds import HDSServer
                self.hds = HDSServer(self.name, self.acc.driver.loop)
                if self.recorder is not None:
                    self.recorder.attach(self.hds)
            port, accessory_salt = self.hds.prepare(shared, controller_salt, str(self._ds_client))
        except Exception:
            _LOGGER.warning("[%s] HKSV: couldn't start the data stream listener", self.name, exc_info=True)
            return failure
        _LOGGER.debug("[%s] HKSV: hub %s asked for a data stream - expecting it on port %d",
                      self.name, self._ds_client[0] if self._ds_client else "?", port)
        params = tlv.encode(b"\x01", struct.pack("<H", port))
        stripped = tlv.encode(DS_RESPONSE_STATUS, DS_STATUS_SUCCESS, b"\x02", params)
        # Reads of the characteristic return the response without the salt
        self.char_setup_ds.value = base64.b64encode(stripped).decode()
        return base64.b64encode(stripped + tlv.encode(b"\x03", accessory_salt)).decode()

    # ----------------------------------------------------------- persistence
    def _persist(self):
        if not self.storage_path:
            return
        state = {
            "config_hash": self._config_hash,
            "selected": self.selected_b64,
            "recording_active": int(self.char_recording_active.value or 0),
            "recording_audio_active": int(self.char_recording_audio.value or 0),
            "camera_active": int(self.char_camera_active.value or 0),
            "event_snapshots": int(self.char_event_snapshots.value or 0),
            "periodic_snapshots": int(self.char_periodic_snapshots.value or 0),
            "streaming_active": [int(c.value or 0) for c in self._rtp_active],
        }
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            tmp = self.storage_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, self.storage_path)
        except OSError:
            _LOGGER.debug("[%s] HKSV: couldn't save state", self.name, exc_info=True)

    def _restore(self):
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path) as f:
                state = json.load(f)
        except (OSError, ValueError):
            return
        # Only restore the hub's selection if what we support hasn't changed
        if state.get("selected") and state.get("config_hash") == self._config_hash:
            try:
                self.selected = self.parse_selected(state["selected"])
                self.selected_b64 = state["selected"]
                self.char_selected.set_value(self.selected_b64)
            except Exception:
                pass
        self.recording_active = bool(state.get("recording_active", 0))
        self.char_recording_active.set_value(int(self.recording_active))
        self.char_recording_audio.set_value(int(state.get("recording_audio_active", 0)))
        self.char_camera_active.set_value(int(state.get("camera_active", 1)))
        self.char_event_snapshots.set_value(int(state.get("event_snapshots", 1)))
        self.char_periodic_snapshots.set_value(int(state.get("periodic_snapshots", 1)))
        for char, val in zip(self._rtp_active, state.get("streaming_active", [])):
            char.set_value(int(val))
        if self.char_status_active is not None:
            self.char_status_active.set_value(bool(self.char_camera_active.value))
        _LOGGER.info("[%s] HKSV: restored state (recording %s%s)", self.name,
                     "enabled" if self.recording_active else "disabled",
                     ", configuration selected" if self.selected else "")
