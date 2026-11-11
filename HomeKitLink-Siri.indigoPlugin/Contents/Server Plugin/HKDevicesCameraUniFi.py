#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
UniFi Protect cameras, from the cameras another Indigo plugin creates:
  - Durosity UniFi plugin   (com.durosity.indigoplugin.unifi, device type protectCamera)
  - kw123 uniFiAP plugin    (com.karlwachs.uniFiAP, device type camera_protect)

Streaming is the SecuritySpy camera (plain RTSP/RTSPS input, Opus audio proxy).  Only the stream
choice and the snapshot differ:
  - At home (HomeKit asks for 1280 wide or more): the High Protect stream, passed straight
    through when ffprobe says it is safe (or Medium, if High is bigger than 1920 wide).
  - Away (smaller / lower bitrate request): the Low Protect stream, re-encoded to the bitrate
    HomeKit asks for.  Low is ~640x360, so the re-encode is cheap and only runs while viewing.
Nothing here runs unless a UniFi camera is published.
"""

import logging
import warnings

try:
    import indigo
except ImportError:
    pass

from HKConstants import (
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    CONF_VIDEO_MAP,
)
from HKDevicesCameraSecuritySpy import SecuritySpyCamera

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

UNIFI_DUROSITY_ID = "com.durosity.indigoplugin.unifi"
UNIFI_KW123_ID = "com.karlwachs.uniFiAP"
UNIFI_CAMERA_TYPES = {
    UNIFI_DUROSITY_ID: ("protectCamera",),
    UNIFI_KW123_ID: ("camera_protect",),
}

## Durosity: True while that detection is active
DUROSITY_MOTION_STATES = ("motionDetected", "personDetected", "vehicleDetected")
## kw123: "status" is "CONNECTED" when idle, else the event type(s), comma separated
KW123_MOTION_EVENTS = {"motion", "event", "person", "vehicle", "animal", "package", "face", "licenseplate", "smartdetect"}


def is_unifi_camera(dev):
    return dev.deviceTypeId in UNIFI_CAMERA_TYPES.get(dev.pluginId, ())


def _state(dev, key):
    try:
        return dev.states.get(key, "")
    except Exception:
        return ""


def stream_urls(dev):
    """{"high":, "medium":, "low":} RTSP(S) URLs, "" where not available.
    A "Stream URL" pasted into the HomeKitLink device config overrides High (kw123 cameras have no
    stream URL states, so it is the only source there)."""
    urls = {"high": "", "medium": "", "low": ""}
    if dev.pluginId == UNIFI_DUROSITY_ID:
        urls["high"] = str(_state(dev, "rtspUrlHigh") or "").strip()
        urls["medium"] = str(_state(dev, "rtspUrlMedium") or "").strip()
        urls["low"] = str(_state(dev, "rtspUrlLow") or "").strip()
    override = str(dev.pluginProps.get("HomeKit_unifiStreamURL", "") or "").strip()
    if override:
        urls["high"] = override
    if not urls["high"]:
        urls["high"] = urls["medium"] or urls["low"]
    return urls


def mask_url(url):
    """Hide the stream token (anyone with it can watch the camera) for logging."""
    try:
        scheme, rest = url.split("://", 1)
        host = rest.split("/", 1)[0]
        return "{}://{}/****".format(scheme, host)
    except Exception:
        return "****"


def camera_model(dev):
    if dev.pluginId == UNIFI_DUROSITY_ID:
        return str(_state(dev, "model") or "")
    return str(_state(dev, "type") or "")


def is_doorbell(dev):
    return "doorbell" in camera_model(dev).lower()


def motion_active(dev):
    if dev.pluginId == UNIFI_DUROSITY_ID:
        return any(bool(_state(dev, key)) for key in DUROSITY_MOTION_STATES)
    status = str(_state(dev, "status") or "").lower().replace(" ", "")
    return any(token in KW123_MOTION_EVENTS for token in status.split(","))


def doorbell_rang(original_dev, updated_dev):
    """A new ring: the last-ring time changed.  Catches every ring, including a second one
    while the first is still showing."""
    key = "lastDoorbellRing" if updated_dev.pluginId == UNIFI_DUROSITY_ID else "lastRing"
    new = _state(updated_dev, key)
    return bool(new) and new != _state(original_dev, key)


def get_camera_options(plugin, dev):
    """HomeKitLink camera config for a UniFi Protect camera device, or None."""
    urls = stream_urls(dev)
    if not urls["high"]:
        if dev.pluginId == UNIFI_DUROSITY_ID:
            fix = "run the UniFi plugin action 'Enable RTSP Streaming' for this camera (High and Low)"
        else:
            fix = "enable RTSP for this camera in Protect (Settings > Advanced) and paste its URL into 'Stream URL' in this device's HomeKitLink settings"
        plugin.logger.warning("[{}] UniFi camera has no stream URL - {}.".format(dev.name, fix))
        return None

    config = {
        CONF_SUPPORT_AUDIO: dev.pluginProps.get("HomeKit_audioSelector", False),
        CONF_VIDEO_CODEC: "copy",  ## passthrough when ffprobe says it's safe, else transcode
        CONF_AUDIO_CODEC: "libopus",
        CONF_MAX_WIDTH: 1920,
        CONF_MAX_HEIGHT: 1080,
        CONF_MAX_FPS: 30,
        CONF_VIDEO_MAP: "0:v:0",  ## Protect puts audio first
        CONF_AUDIO_MAP: "0:a:0?",
        "useMotionSensor": True,
        "start_commands_extra": "-probesize 32768 -analyzeduration 500000 ",
        CONF_STREAM_SOURCE: urls["high"],
        "UP_name": "UniFi_{}".format(dev.id),  ## snapshot file name
        "UP_deviceId": dev.id,
        "cameraName": dev.name,
        "unifi_urls": urls,
        "unifi_low_url": urls["low"] if urls["low"] != urls["high"] else "",
    }
    if is_doorbell(dev):
        config["DoorBell_ID"] = dev.id  ## the camera is its own doorbell
    else:
        linked = str(dev.pluginProps.get("HomeKit_doorbellId", "") or "")
        if linked not in ("", "-1"):
            config["DoorBell_ID"] = linked
    return config


def choose_home_stream(cam, log):
    """After the startup probe: High bigger than 1920 wide can't be passed through well, so use
    Medium at home instead.  Returns True if the stream changed (probe it again)."""
    video = cam.get("ffprobe_video") or {}
    urls = cam.get("unifi_urls") or {}
    medium = urls.get("medium")
    if video.get("width", 0) > 1920 and medium and cam.get(CONF_STREAM_SOURCE) != medium:
        log("[%s]   High stream is %sx%s - using the Medium stream at home instead.",
            cam.get("cameraName"), video.get("width"), video.get("height"))
        cam[CONF_STREAM_SOURCE] = medium
        if cam.get("unifi_low_url") == medium:
            cam["unifi_low_url"] = ""
        return True
    return False


def fetch_snapshot(plugin, camera, path, width, session):
    """Save a JPEG of the camera to path.  Returns True on success."""
    dev = indigo.devices[int(camera["UP_deviceId"])]
    if dev.pluginId == UNIFI_DUROSITY_ID:
        url = _state(dev, "snapshotUrl")
        controller_id = int(dev.ownerProps.get("controllerId", 0) or 0)  ## ownerProps = the UniFi plugin's own props
        if not url or not controller_id or controller_id not in indigo.devices:
            plugin.logger.debug("[%s] No UniFi snapshot URL / controller", dev.name)
            return False
        api_key = indigo.devices[controller_id].ownerProps.get("networkApiKey", "").strip()
        params = {"highQuality": "true"} if int(width) > 1280 else None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  ## Protect consoles use a self-signed certificate
            r = session.get(url, headers={"X-API-KEY": api_key}, params=params, verify=False, timeout=10)
        if r.status_code != 200 or not r.content:
            plugin.logger.debug("[%s] UniFi snapshot failed, status %s", dev.name, r.status_code)
            return False
        with open(path, "wb") as f:
            f.write(r.content)
        return True

    ## kw123 uniFiAP: its own action fetches the snapshot and writes the file
    kw = indigo.server.getPlugin(UNIFI_KW123_ID)
    if not kw.isEnabled():
        return False
    width = int(width)
    kw.executeAction("CAMERAsnapshotProtect", props={
        "cameraDeviceSelected": str(dev.id),
        "whofImage": "{}/{}".format(width, int(width * 9 / 16)),
        "fileNameOfImage": path,
    })
    return True


class UniFiCamera(SecuritySpyCamera):
    """SecuritySpy camera with the UniFi stream choice and snapshot file."""

    SNAPSHOT_NAME_KEY = "UP_name"

    def _select_source(self, stream_config):
        req_width = stream_config.get("width", 0) or 0
        req_bitrate = stream_config.get("v_max_bitrate", 0) or 0
        low_url = self.config.get("unifi_low_url")
        if low_url and ((0 < req_width < 1280) or (0 < req_bitrate < 299)):
            _LOGGER.info("[%s] Remote / low-bandwidth request (%sx%s @ %sk): using the Protect Low stream, re-encoded",
                         self.display_name, req_width, stream_config.get("height"), req_bitrate)
            return low_url, self.config.get("ffprobe_low"), "libx264"
        return super()._select_source(stream_config)
