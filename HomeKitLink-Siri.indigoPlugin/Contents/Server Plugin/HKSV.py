"""HomeKit Secure Video (HKSV) for HomeKitLink cameras - phase 1.

Only used for a camera that has an "HKSV Recorder" device. Nothing here runs
for other cameras: the services, the HomeKit Data Stream listener and the
saved state all belong to that camera alone.

Phase 1 advertises the recording services, saves the home hub's chosen
recording configuration and the Home app's switches, and answers the hub's
HomeKit Data Stream (encrypted, hello only). Recording itself (prebuffer and
sending clips) is phase 2, so the hub's recording requests are refused.

TLV layouts follow HAP-NodeJS lib/camera/RecordingManagement.js, via PR #42
(Durosity). Changes from the PR: the hub's HAP connection is taken from the
write itself rather than a module global shared by all bridges; an
unreadable configuration is refused instead of accepted; state is saved per
Indigo camera device; and the Data Stream listener only accepts the hub that
set it up.

Services added to the camera accessory:
  * CameraOperatingMode            (HomeKitCameraActive, EventSnapshotsActive, PeriodicSnapshotsActive)
  * CameraRecordingManagement      (Active, Supported*/SelectedCameraRecordingConfiguration, RecordingAudioActive)
  * DataStreamTransportManagement  (SetupDataStreamTransport, SupportedDataStreamTransportConfiguration, Version)
plus an Active characteristic on each CameraRTPStreamManagement service.
"""

import base64
import hashlib
import json
import logging
import os
import struct
import time

from pyhap import tlv
from pyhap.characteristic import Characteristic

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn.HKSV")

# --- Characteristic and service definitions (HAP-NodeJS), registered only when used ---
_CHARS = {
    "EventSnapshotsActive": {"Format": "uint8", "Permissions": ["pr", "pw", "ev"], "UUID": "00000223-0000-1000-8000-0026BB765291", "ValidValues": {"Disable": 0, "Enable": 1}},
    "HomeKitCameraActive": {"Format": "uint8", "Permissions": ["pr", "pw", "ev"], "UUID": "0000021B-0000-1000-8000-0026BB765291", "ValidValues": {"Off": 0, "On": 1}},
    "PeriodicSnapshotsActive": {"Format": "uint8", "Permissions": ["pr", "pw", "ev"], "UUID": "00000225-0000-1000-8000-0026BB765291", "ValidValues": {"Disable": 0, "Enable": 1}},
    "RecordingAudioActive": {"Format": "uint8", "Permissions": ["pr", "pw", "ev", "tw"], "UUID": "00000226-0000-1000-8000-0026BB765291", "ValidValues": {"Disable": 0, "Enable": 1}},
    "SelectedCameraRecordingConfiguration": {"Format": "tlv8", "Permissions": ["pr", "pw", "ev"], "UUID": "00000209-0000-1000-8000-0026BB765291"},
    "SetupDataStreamTransport": {"Format": "tlv8", "Permissions": ["pr", "pw", "wr"], "UUID": "00000131-0000-1000-8000-0026BB765291"},
    "SupportedAudioRecordingConfiguration": {"Format": "tlv8", "Permissions": ["pr", "ev"], "UUID": "00000207-0000-1000-8000-0026BB765291"},
    "SupportedCameraRecordingConfiguration": {"Format": "tlv8", "Permissions": ["pr", "ev"], "UUID": "00000205-0000-1000-8000-0026BB765291"},
    "SupportedDataStreamTransportConfiguration": {"Format": "tlv8", "Permissions": ["pr"], "UUID": "00000130-0000-1000-8000-0026BB765291"},
    "SupportedVideoRecordingConfiguration": {"Format": "tlv8", "Permissions": ["pr", "ev"], "UUID": "00000206-0000-1000-8000-0026BB765291"},
}
_SERVICES = {
    "CameraOperatingMode": {"OptionalCharacteristics": ["PeriodicSnapshotsActive"], "RequiredCharacteristics": ["EventSnapshotsActive", "HomeKitCameraActive"], "UUID": "0000021A-0000-1000-8000-0026BB765291"},
    "CameraRecordingManagement": {"OptionalCharacteristics": ["RecordingAudioActive"], "RequiredCharacteristics": ["Active", "SelectedCameraRecordingConfiguration", "SupportedAudioRecordingConfiguration", "SupportedCameraRecordingConfiguration", "SupportedVideoRecordingConfiguration"], "UUID": "00000204-0000-1000-8000-0026BB765291"},
    "DataStreamTransportManagement": {"OptionalCharacteristics": [], "RequiredCharacteristics": ["SetupDataStreamTransport", "SupportedDataStreamTransportConfiguration", "Version"], "UUID": "00000129-0000-1000-8000-0026BB765291"},
}

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
VIDEO_ATTR_WIDTH = b"\x01"
VIDEO_ATTR_HEIGHT = b"\x02"
VIDEO_ATTR_FPS = b"\x03"

SUPPORTED_AUDIO_CODEC_CONFIGURATION = b"\x01"
AUDIO_CODEC_TYPE = b"\x01"
AUDIO_CODEC_PARAMETERS = b"\x02"
AUDIO_PARAM_CHANNEL = b"\x01"
AUDIO_PARAM_BIT_RATE = b"\x02"
AUDIO_PARAM_SAMPLE_RATE = b"\x03"

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

TLV_DELIMITER = b"\x00\x00"

PREBUFFER_MS = 4000
FRAGMENT_MS = 4000
RECORDING_RESOLUTIONS = [(1920, 1080), (1280, 720), (640, 360)]
CONF_MAX_WIDTH = "max_width"      # as HKConstants (which needs indigo, so isn't imported here)
CONF_MAX_HEIGHT = "max_height"


def register_resources(loader):
    """Add the HKSV characteristic/service definitions to a pyhap loader.
    Only adds names it doesn't already have, so nothing else changes."""
    for name, d in _CHARS.items():
        loader.char_types.setdefault(name, d)
    for name, d in _SERVICES.items():
        loader.serv_types.setdefault(name, d)


class _WriterAwareChar(Characteristic):
    """Remembers which HAP connection last wrote it (the Data Stream keys come
    from that connection's session secret)."""

    def client_update_value(self, value, sender_client_addr=None):
        self.last_writer = sender_client_addr
        return super().client_update_value(value, sender_client_addr)


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


def recording_resolutions(camera_config):
    """Recording sizes to offer: the standard ones up to the camera's maximum."""
    try:
        max_w = int(camera_config.get(CONF_MAX_WIDTH, 1920) or 1920)
        max_h = int(camera_config.get(CONF_MAX_HEIGHT, 1080) or 1080)
    except (TypeError, ValueError):
        max_w, max_h = 1920, 1080
    sizes = [(w, h) for (w, h) in RECORDING_RESOLUTIONS if w <= max_w and h <= max_h]
    return sizes or [RECORDING_RESOLUTIONS[-1]]


def describe_selected(parsed):
    v, a = parsed["video"], parsed["audio"]
    return "{}x{}@{}fps H.264 {} {}, {} kbps, keyframe every {} ms; {} {} Hz; prebuffer {} ms".format(
        v["width"], v["height"], v["fps"], v["profile"], v["level"], v["bitrate_kbps"],
        v["iframe_interval_ms"], a["codec"], a["sample_rate"], parsed["prebuffer_ms"])


class HKSVRecording:
    """Adds and manages the HKSV services on one camera accessory."""

    def __init__(self, accessory, camera_config, state_path, recorder_id=None, enabled=True, on_state=None):
        self.acc = accessory
        self.name = accessory.display_name
        self.state_path = state_path
        self.recorder_id = recorder_id
        self.on_state = on_state          # callback(dict of Indigo states) - runs on the bridge thread
        self.enabled = bool(enabled)      # the Recorder device's Enable/Disable communication
        self.stopped = False              # the bridge has stopped
        self.selected = None              # parsed selected configuration
        self.selected_b64 = ""
        self.recording_active = False
        self.hds = None
        self.motion_char = getattr(accessory, "char_motion_detected", None)
        doorbell = getattr(accessory, "_char_doorbell_detected", None) is not None

        register_resources(accessory.driver.loader)
        self._supported_camera = self._supported_camera_config(doorbell)
        self._supported_video = self._supported_video_config(recording_resolutions(camera_config))
        self._supported_audio = self._supported_audio_config()
        self._config_hash = hashlib.sha256(
            (self._supported_camera + self._supported_video + self._supported_audio).encode()).hexdigest()

        self._build_services()
        self._restore()
        self._wrap_stop()
        if self.motion_char is None:
            _LOGGER.warning("[%s] HKSV: this camera has no motion sensor in HomeKit, so the hub will never "
                            "record it. Turn on the camera's motion sensor in its HomeKitLink settings", self.name)
        _LOGGER.info("[%s] HomeKit Secure Video services added (recording itself comes in a later version)", self.name)
        self.publish_state()

    # ------------------------------------------------------------------ TLVs
    @staticmethod
    def _supported_camera_config(doorbell):
        triggers = EVENT_TRIGGER_MOTION | (EVENT_TRIGGER_DOORBELL if doorbell else 0)
        container = tlv.encode(
            MEDIA_CONTAINER_TYPE, b"\x00",  # fragmented MP4
            MEDIA_CONTAINER_PARAMETERS, tlv.encode(MEDIA_CONTAINER_FRAGMENT_LENGTH, struct.pack("<I", FRAGMENT_MS)))
        return tlv.encode(
            SUPPORTED_CAMERA_PREBUFFER_LENGTH, struct.pack("<I", PREBUFFER_MS),
            SUPPORTED_CAMERA_EVENT_TRIGGER_OPTIONS, struct.pack("<Q", triggers),
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

        # SetupDataStreamTransport must know which HAP connection wrote it
        ds = loader.get_service("DataStreamTransportManagement")
        setup = _WriterAwareChar.from_dict("SetupDataStreamTransport", dict(_CHARS["SetupDataStreamTransport"]))
        setup.last_writer = None
        ds.characteristics = [c for c in ds.characteristics if c.display_name != "SetupDataStreamTransport"]
        ds.add_characteristic(setup)
        acc.add_service(ds)
        ds.configure_char("SupportedDataStreamTransportConfiguration",
                          value=tlv.encode(DS_TRANSFER_TRANSPORT_CONFIGURATION,
                                           tlv.encode(DS_TRANSPORT_TYPE, DS_TRANSPORT_TCP), to_base64=True))
        ds.configure_char("Version", value="1.0")
        self.char_setup_ds = ds.configure_char("SetupDataStreamTransport", value="",
                                               setter_callback=self._on_setup_data_stream)

        rm = acc.add_preload_service("CameraRecordingManagement", chars=["RecordingAudioActive"])
        for cname, val in (("SupportedCameraRecordingConfiguration", self._supported_camera),
                           ("SupportedVideoRecordingConfiguration", self._supported_video),
                           ("SupportedAudioRecordingConfiguration", self._supported_audio)):
            rm.configure_char(cname, value=val)
        self.char_selected = rm.configure_char("SelectedCameraRecordingConfiguration", value="",
                                               setter_callback=self._on_selected_configuration,
                                               getter_callback=lambda: self.selected_b64 or "")
        self.char_recording_active = rm.configure_char("Active", value=0, setter_callback=self._on_recording_active)
        self.char_recording_audio = rm.configure_char("RecordingAudioActive", value=0,
                                                      setter_callback=self._on_simple("RecordingAudioActive"))
        rm.add_linked_service(ds)

        # Motion sensor reports StatusActive, mirroring HomeKitCameraActive, and is
        # linked to recording management so the hub knows what triggers a
        # recording (as HAP-NodeJS CameraController; PR #42 left this out)
        self.char_status_active = None
        motion_service = getattr(self.motion_char, "service", None)
        if motion_service is not None:
            rm.add_linked_service(motion_service)
            try:
                char = loader.get_char("StatusActive")
                char.set_value(True)
                self._attach(motion_service, char)
                self.char_status_active = char
            except Exception:
                _LOGGER.debug("[%s] HKSV: couldn't add StatusActive to the motion sensor", self.name, exc_info=True)

        # A video doorbell's Doorbell service is the accessory's primary service
        # (as HAP-NodeJS DoorbellController). Only done here, for HKSV cameras.
        doorbell_service = getattr(getattr(acc, "_char_doorbell_detected", None), "service", None)
        if doorbell_service is not None:
            acc.set_primary_service(doorbell_service)

    def _attach(self, service, char):
        """Add a characteristic to a service that's already on the accessory,
        giving it a broker and a (stored) IID as add_service would."""
        service.add_characteristic(char)
        char.broker = self.acc
        self.acc.iid_manager.assign(char)

    def _wrap_stop(self):
        """Close the Data Stream listener when the bridge stops."""
        original = self.acc.stop

        async def stop():
            self.stopped = True
            self.close()
            self.publish_state()
            await original()
        self.acc.stop = stop

    def close(self):
        if self.hds is not None:
            try:
                self.hds.close()
            except Exception:
                _LOGGER.debug("[%s] HKSV: data stream close failed", self.name, exc_info=True)
            self.hds = None

    # -------------------------------------------------------- Indigo states
    def state(self):
        hubs = len(self.hds.connections) if self.hds is not None else 0
        last = getattr(self.hds, "last_contact_time", None) if self.hds is not None else None
        if self.stopped:
            status = "Bridge stopped"
        elif not self.enabled:
            status = "Disabled"
        elif not (self.char_camera_active.value or 0):
            status = "Camera off in Home app"
        elif not self.recording_active:
            status = "Recording off in Home app"
        elif not self.selected:
            status = "Waiting for hub"
        else:
            status = "Ready (recording not yet supported)"
        return {
            "status": status,
            "homeAppCameraOn": bool(self.char_camera_active.value),
            "homeAppRecording": bool(self.recording_active),
            "homeAppRecordingAudio": bool(self.char_recording_audio.value),
            "selectedConfig": describe_selected(self.selected) if self.selected else "",
            "hubsConnected": hubs,
            "lastHubContact": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)) if last else "",
        }

    def publish_state(self):
        if self.on_state is None:
            return
        try:
            self.on_state(self.state())
        except Exception:
            _LOGGER.debug("[%s] HKSV: state update failed", self.name, exc_info=True)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.publish_state()

    # -------------------------------------------------------------- setters
    # The Home app re-writes these switches often; only log real changes.
    def _changed(self, key, value):
        last = getattr(self, "_last_values", None)
        if last is None:
            last = self._last_values = {}
        if last.get(key) == value:
            return False
        last[key] = value
        return True

    def _on_simple(self, label):
        def setter(value):
            if self._changed(label, value):
                _LOGGER.info("[%s] HKSV: %s set to %s", self.name, label, value)
                self._persist()
                self.publish_state()
        return setter

    def _on_streaming_active(self, value):
        if self._changed("streaming", value):
            _LOGGER.info("[%s] HKSV: live streaming %s", self.name, "allowed" if value else "turned off in the Home app")
            self._persist()

    def _on_camera_active(self, value):
        if self.char_status_active is not None:
            self.char_status_active.set_value(bool(value))
        if self._changed("camera", value):
            _LOGGER.info("[%s] HKSV: camera %s in the Home app", self.name, "on" if value else "off")
            self._persist()
        self.publish_state()

    def _on_recording_active(self, value):
        self.recording_active = bool(value)
        if self._changed("recording", value):
            _LOGGER.info("[%s] HKSV: recording %s in the Home app%s", self.name, "allowed" if value else "turned off",
                         "" if (not value or self.selected) else " (the hub hasn't chosen a recording format yet)")
            self._persist()
        self.publish_state()

    def _on_selected_configuration(self, value):
        try:
            parsed = self.parse_selected(value)
        except Exception:
            _LOGGER.warning("[%s] HKSV: couldn't read the recording format the hub chose", self.name)
            _LOGGER.debug("raw value %r", value, exc_info=True)
            # Refuse it: the hub mustn't think recording is configured (PR review 2.8)
            raise ValueError("unreadable SelectedCameraRecordingConfiguration")
        changed = value != self.selected_b64
        self.selected_b64 = value
        self.selected = parsed
        if changed:
            _LOGGER.info("[%s] HKSV: hub chose %s, fragments %d ms, triggers %s", self.name,
                         describe_selected(parsed), parsed["fragment_ms"],
                         "+".join(n for b, n in ((1, "motion"), (2, "doorbell")) if parsed["event_triggers"] & b) or "none")
            self._persist()
        self.publish_state()

    def _on_setup_data_stream(self, value):
        """Prepare a HomeKit Data Stream session for the hub (write response)."""
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
        client = getattr(self.char_setup_ds, "last_writer", None)
        proto = self.acc.driver.http_server.connections.get(client) if client else None
        shared = getattr(proto, "hds_shared_secret", None)
        sockname = proto.transport.get_extra_info("sockname") if proto is not None and proto.transport else None
        if not shared or not sockname:
            _LOGGER.warning("[%s] HKSV: data stream requested by %s but its HAP session isn't available",
                            self.name, client)
            return failure
        try:
            if self.hds is None:
                from hds import HDSServer
                self.hds = HDSServer(self.name, self.acc.driver.loop, on_change=self.publish_state)
            port, accessory_salt = self.hds.prepare(shared, controller_salt, client[0], sockname[0])
        except Exception:
            _LOGGER.warning("[%s] HKSV: couldn't start the data stream listener", self.name, exc_info=True)
            return failure
        _LOGGER.debug("[%s] HKSV: hub %s asked for a data stream - expecting it on %s port %d",
                      self.name, client[0], sockname[0], port)
        params = tlv.encode(b"\x01", struct.pack("<H", port))
        stripped = tlv.encode(DS_RESPONSE_STATUS, DS_STATUS_SUCCESS, b"\x02", params)
        # Reads of the characteristic return the response without the salt
        self.char_setup_ds.value = base64.b64encode(stripped).decode()
        return base64.b64encode(stripped + tlv.encode(b"\x03", accessory_salt)).decode()

    # ----------------------------------------------------------- persistence
    def _persist(self):
        if not self.state_path:
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
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, self.state_path)
        except OSError:
            _LOGGER.debug("[%s] HKSV: couldn't save state", self.name, exc_info=True)

    def _restore(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path) as f:
                state = json.load(f)
        except (OSError, ValueError):
            return
        # Only restore the hub's choice if what we offer hasn't changed
        if state.get("selected") and state.get("config_hash") == self._config_hash:
            try:
                self.selected = self.parse_selected(state["selected"])
                self.selected_b64 = state["selected"]
                self.char_selected.set_value(self.selected_b64)
            except Exception:
                self.selected, self.selected_b64 = None, ""
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
        _LOGGER.info("[%s] HKSV: restored Home app settings (recording %s%s)", self.name,
                     "allowed" if self.recording_active else "off",
                     ", format chosen" if self.selected else "")
