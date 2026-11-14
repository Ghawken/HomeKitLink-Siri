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
import os
import re
import urllib.parse
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
UNIFI_PACKAGE_TYPE = "protectPackageCamera"   ## Durosity: a G4 Doorbell Pro / G6 Entry's second (package) lens
UNIFI_CAMERA_TYPES = {
    UNIFI_DUROSITY_ID: ("protectCamera", UNIFI_PACKAGE_TYPE),
    UNIFI_KW123_ID: ("camera_protect",),
}

## Durosity: True while that detection is active
DUROSITY_MOTION_STATES = ("motionDetected", "personDetected", "vehicleDetected")
DUROSITY_PACKAGE_MOTION_STATES = ("packageDetected", "motionDetected", "personDetected")
## kw123: "status" is "CONNECTED" when idle, else the event type(s), comma separated
KW123_MOTION_EVENTS = {"motion", "event", "person", "vehicle", "animal", "package", "face", "licenseplate", "smartdetect"}


def is_unifi_camera(dev):
    return dev.deviceTypeId in UNIFI_CAMERA_TYPES.get(dev.pluginId, ())


def is_package_camera(dev):
    return dev.pluginId == UNIFI_DUROSITY_ID and dev.deviceTypeId == UNIFI_PACKAGE_TYPE


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
    if is_package_camera(dev):
        urls["high"] = str(_state(dev, "rtspUrlPackage") or "").strip()   ## the package lens has one stream
    elif dev.pluginId == UNIFI_DUROSITY_ID:
        urls["high"] = str(_state(dev, "rtspUrlHigh") or "").strip()
        urls["medium"] = str(_state(dev, "rtspUrlMedium") or "").strip()
        urls["low"] = str(_state(dev, "rtspUrlLow") or "").strip()
    override = str(dev.pluginProps.get("HomeKit_unifiStreamURL", "") or "").strip()
    if override:
        urls["high"] = override
    if not urls["high"]:
        urls["high"] = urls["medium"] or urls["low"]
    return urls


_URL_TOKEN = re.compile(r"(rtsps?://[^/\s'\",]+/)[^\s:'\",}]+")


def mask_url(text):
    """Hide stream tokens (anyone with one can watch the camera) in text for logging."""
    return _URL_TOKEN.sub(r"\1****", str(text))


def camera_model(dev):
    if dev.pluginId == UNIFI_DUROSITY_ID:
        return str(_state(dev, "model") or "")
    return str(_state(dev, "type") or "")


def is_doorbell(dev):
    """A doorbell by model, or ticked "Treat as doorbell" in its HomeKitLink settings.
    Never the package lens (the main lens is the doorbell)."""
    if is_package_camera(dev):
        return False
    return "doorbell" in camera_model(dev).lower() or bool(dev.pluginProps.get("HomeKit_unifiDoorbell", False))


def motion_active(dev):
    if is_package_camera(dev):
        return any(bool(_state(dev, key)) for key in DUROSITY_PACKAGE_MOTION_STATES)
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


def talkback_info(dev):
    """What the audio proxy needs to open a Protect talkback session (two-way audio):
    console host:port, Protect camera id and API key.  Durosity UniFi plugin only (uniFiAP
    keeps its credentials private).  Returns None if anything is missing."""
    if dev.pluginId != UNIFI_DUROSITY_ID or is_package_camera(dev):
        return None
    camera_id = str(dev.ownerProps.get("cameraId", "") or "").strip()
    controller_id = int(dev.ownerProps.get("controllerId", 0) or 0)
    if not camera_id or not controller_id or controller_id not in indigo.devices:
        return None
    controller = indigo.devices[controller_id].ownerProps
    api_key = str(controller.get("networkApiKey", "") or "").strip()
    host = urllib.parse.urlsplit(str(_state(dev, "snapshotUrl") or "")).netloc  ## keeps a custom port
    if not host:
        address = str(controller.get("address", "") or "").strip()
        port = str(controller.get("port", "") or "").strip()
        host = "{}:{}".format(address, port) if address and port else address
    if not (api_key and host):
        return None
    return {"host": host, "camera_id": camera_id, "api_key": api_key}


def get_camera_options(plugin, dev):
    """HomeKitLink camera config for a UniFi Protect camera device, or None."""
    urls = stream_urls(dev)
    if not urls["high"]:
        if is_package_camera(dev):
            fix = "run the UniFi plugin action 'Enable RTSP Streaming' for the doorbell so its package lens has an rtspUrlPackage"
        elif dev.pluginId == UNIFI_DUROSITY_ID:
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
    if is_package_camera(dev):
        config["UP_package"] = True
    ## Portrait cameras (some doorbells): offer HomeKit portrait sizes, from the size the
    ## startup stream check saw last time. Landscape cameras keep the standard sizes.
    portrait = portrait_resolutions(dev.pluginProps.get("HomeKit_unifiStreamSize", ""))
    if portrait:
        config["custom_resolutions"] = portrait
        config[CONF_MAX_WIDTH], config[CONF_MAX_HEIGHT] = portrait[0][0], portrait[0][1]
    if is_doorbell(dev):
        config["DoorBell_ID"] = dev.id  ## the camera is its own doorbell
    else:
        linked = str(dev.pluginProps.get("HomeKit_doorbellId", "") or "")
        if linked not in ("", "-1"):
            config["DoorBell_ID"] = linked

    ## Two-way audio (talk) - opt-in per camera
    two_way = "no"
    if dev.pluginProps.get("HomeKit_unifiTwoWay", False):
        if is_package_camera(dev):
            plugin.logger.warning("[{}] Two-way audio isn't available on a package lens - use the doorbell's main camera.".format(dev.name))
        elif dev.pluginId != UNIFI_DUROSITY_ID:
            plugin.logger.warning("[{}] Two-way audio needs the UniFi plugin (Durosity) - not available for uniFiAP cameras.".format(dev.name))
        elif not config[CONF_SUPPORT_AUDIO]:
            plugin.logger.warning("[{}] Two-way audio needs Support Audio turned on for this camera.".format(dev.name))
        elif talkback_info(dev) is None:
            plugin.logger.warning("[{}] Two-way audio: no Protect camera id, console address or API key found on the UniFi devices.".format(dev.name))
        else:
            config["two_way_audio"] = True
            config["speaker_service"] = True  ## HomeKit shows the talk button when the camera has a Speaker
            two_way = "yes"
    yes_no = lambda v: "yes" if v else "no"
    plugin.logger.info("[{}] UniFi Protect {} ({}, {}): High {}, Medium {}, Low {}, Stream URL override {}, doorbell {}, motion {}, audio {}, two-way {}{}".format(
        dev.name, "package camera" if is_package_camera(dev) else "camera",
        "UniFi plugin" if dev.pluginId == UNIFI_DUROSITY_ID else "uniFiAP plugin", camera_model(dev) or "model unknown",
        yes_no(urls["high"]), yes_no(urls["medium"]), yes_no(urls["low"]),
        yes_no(dev.pluginProps.get("HomeKit_unifiStreamURL")),
        "built in" if is_doorbell(dev) else ("linked" if "DoorBell_ID" in config else "no"),
        yes_no(dev.pluginProps.get("HomeKit_motionEnabled", True)), yes_no(config[CONF_SUPPORT_AUDIO]), two_way,
        ", portrait {}x{}".format(*portrait[0]) if portrait else ""))
    return config


def portrait_resolutions(size_text):
    """HomeKit sizes for a portrait stream "WxH" (taller than wide), largest first, or [].
    Each keeps the stream's shape, with even sizes, up to 1080 wide."""
    try:
        w, h = (int(v) for v in str(size_text).lower().split("x"))
    except (TypeError, ValueError):
        return []
    if w <= 0 or h <= w:
        return []
    out = []
    for target_w in (1080, 720, 480, 360, 240):
        tw = min(target_w, w)
        th = int(round(h * tw / w / 2.0)) * 2
        tw -= tw % 2
        if (tw, th) not in out:
            out.append((tw, th))
    return out


def remember_stream_size(dev, video):
    """Save the stream size the startup check saw (used for portrait sizes at the next bridge start).
    Returns True if it changed in a way that matters (portrait or not)."""
    try:
        size = "{}x{}".format(int(video["width"]), int(video["height"]))
    except (KeyError, TypeError, ValueError):
        return False
    old = dev.pluginProps.get("HomeKit_unifiStreamSize", "")
    if old == size:
        return False
    props = dev.pluginProps
    props["HomeKit_unifiStreamSize"] = size
    dev.replacePluginPropsOnServer(props)
    return bool(portrait_resolutions(old)) != bool(portrait_resolutions(size))


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
    """Save a JPEG of the camera to path.  Returns True on success.
    Logs (info) the first failure and the recovery, not every attempt."""
    try:
        ok, why = _fetch_snapshot(plugin, camera, path, width, session)
    except Exception as e:
        ok, why = False, mask_url(e)
    if not ok and why == _PACKAGE_NOT_READY:
        return False      ## the first background grab is still running
    if ok != camera.get("_snapshot_ok"):
        if ok:
            plugin.logger.info("[{}] UniFi snapshots working".format(camera.get("cameraName")))
        else:
            plugin.logger.warning("[{}] UniFi snapshot failed: {}".format(camera.get("cameraName"), why))
        camera["_snapshot_ok"] = ok
    return ok


_package_grabs = set()   ## camera device ids with a frame grab running
_PACKAGE_NOT_READY = "first package lens image not ready yet"


def _package_snapshot(plugin, camera, path, width):
    """Protect's snapshot API returns the main lens, so the package lens's snapshot is a frame
    grabbed from its own stream - in a background thread, so the shared snapshot thread
    never waits for it (up to 12 s). Returns the last grabbed image."""
    import subprocess
    import threading
    dev_id = int(camera["UP_deviceId"])
    if dev_id not in _package_grabs:
        _package_grabs.add(dev_id)

        def grab():
            tmp = path + ".grab.jpg"
            try:
                width_px = max(320, min(int(width or 640), 1920))
                r = subprocess.run([plugin.ffmpeg_command_line, "-hide_banner", "-loglevel", "error",
                                    "-rtsp_transport", "tcp", "-i", camera.get(CONF_STREAM_SOURCE, ""),
                                    "-frames:v", "1", "-vf", "scale={}:-2".format(width_px), "-q:v", "4",
                                    "-y", "-f", "image2", tmp], capture_output=True, timeout=12)
                if r.returncode == 0 and os.path.exists(tmp):
                    os.replace(tmp, path)
                else:
                    camera["_package_error"] = mask_url((r.stderr or b"").decode(errors="replace").strip()[-160:]) or "no image"
            except Exception as e:  # noqa: BLE001
                camera["_package_error"] = mask_url(e)
            finally:
                _package_grabs.discard(dev_id)
        threading.Thread(target=grab, daemon=True, name="HKLS-unifi-package-snap").start()
    if os.path.exists(path):
        return True, ""
    return False, camera.get("_package_error") or _PACKAGE_NOT_READY


def _fetch_snapshot(plugin, camera, path, width, session):
    dev = indigo.devices[int(camera["UP_deviceId"])]
    if camera.get("UP_package"):
        return _package_snapshot(plugin, camera, path, width)
    if dev.pluginId == UNIFI_DUROSITY_ID:
        url = _state(dev, "snapshotUrl")
        controller_id = int(dev.ownerProps.get("controllerId", 0) or 0)  ## ownerProps = the UniFi plugin's own props
        if not url or not controller_id or controller_id not in indigo.devices:
            return False, "no snapshotUrl state or UniFi controller device"
        api_key = indigo.devices[controller_id].ownerProps.get("networkApiKey", "").strip()
        params = {"highQuality": "true"} if int(width) > 1280 else None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  ## Protect consoles use a self-signed certificate
            r = session.get(url, headers={"X-API-KEY": api_key}, params=params, verify=False, timeout=10)
        if r.status_code != 200 or not r.content:
            hint = {401: " - check the controller's API key", 403: " - check the API key's permissions", 429: " - Protect rate limit"}.get(r.status_code, "")
            return False, "HTTP {}{}".format(r.status_code, hint)
        with open(path, "wb") as f:
            f.write(r.content)
        return True, ""

    ## kw123 uniFiAP: its own action fetches the snapshot and writes the file
    kw = indigo.server.getPlugin(UNIFI_KW123_ID)
    if not kw.isEnabled():
        return False, "uniFiAP plugin not enabled"
    before = os.path.getmtime(path) if os.path.exists(path) else 0
    width = int(width)
    kw.executeAction("CAMERAsnapshotProtect", props={
        "cameraDeviceSelected": str(dev.id),
        "whofImage": "{}/{}".format(width, int(width * 9 / 16)),
        "fileNameOfImage": path,
    })
    if not os.path.exists(path) or os.path.getmtime(path) == before:
        return False, "uniFiAP 'CAMERAS get Snapshot' action wrote no image"
    return True, ""


class UniFiCamera(SecuritySpyCamera):
    """SecuritySpy camera with the UniFi stream choice and snapshot file."""

    SNAPSHOT_NAME_KEY = "UP_name"

    def _mask(self, text):
        return mask_url(text)

    def _talkback_config(self):
        """Two-way audio target, built fresh for each stream (it holds the Protect API key,
        so it is never stored in the camera config or logged)."""
        if not self.config.get("two_way_audio"):
            return None
        try:
            info = talkback_info(indigo.devices[int(self.config["UP_deviceId"])])
        except Exception:
            _LOGGER.debug("[%s] Two-way audio: couldn't get talkback details", self.display_name, exc_info=True)
            return None
        if info is None:
            _LOGGER.warning("[%s] Two-way audio: Protect details missing - talk is off for this stream", self.display_name)
            return None
        info["name"] = self.display_name
        info["echo_suppress"] = bool(getattr(self.plugin, "talkEchoSuppress", True))
        _LOGGER.debug("[%s] Two-way audio enabled for this stream (console %s)", self.display_name, info["host"])
        return info

    def _select_source(self, stream_config):
        req_width = stream_config.get("width", 0) or 0
        req_bitrate = stream_config.get("v_max_bitrate", 0) or 0
        low_url = self.config.get("unifi_low_url")
        if low_url and ((0 < req_width < 1280) or (0 < req_bitrate < 299)):
            _LOGGER.info("[%s] Remote / low-bandwidth request (%sx%s @ %sk): using the Protect Low stream, re-encoded",
                         self.display_name, req_width, stream_config.get("height"), req_bitrate)
            return low_url, self.config.get("ffprobe_low"), "libx264"
        return super()._select_source(stream_config)
