![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Camera Setup

HKLS supports live camera streams from **Blue Iris** and **SecuritySpy** directly in the Apple Home app — including live video, Opus audio, doorbell notifications, and motion detection.

---

## Supported Camera Integrations

| System | Plugin Required | Video | Audio | Motion | Doorbell |
|---|---|---|---|---|---|
| **Blue Iris** | Blue Iris Indigo plugin | ✅ | ✅ Opus | ✅ | ✅ |
| **SecuritySpy** | FlyingDiver SecuritySpy plugin | ✅ | ✅ Opus | ✅ | ✅ |
| Other cameras | — | ⚠️ Limited | ❌ | ❌ | ❌ |

> **Other cameras** are not officially supported. For unsupported camera systems, consider running a separate [Homebridge](https://homebridge.io/) instance with an appropriate camera plugin.

---

## Prerequisites

### Blue Iris
1. Install the **Blue Iris** Indigo plugin — HKLS pulls camera info and RTSP URLs from it
2. Configure your BI cameras with RTSP stream access on a reachable URL
3. Install the Blue Iris plugin and ensure BI cameras appear in Indigo

### SecuritySpy
1. Install **FlyingDiver's SecuritySpy** Indigo plugin
2. Configure SecuritySpy cameras to have RTSP access

---

## Adding a Camera to a Bridge

1. Open the HomeKitLink Bridge config dialog
2. In the device filter, select **Cameras**
3. Select your BI or SecuritySpy camera device from the list
4. Select HomeKit type: **Camera** (auto-detected for camera devices)
5. Configure the options that appear:
   - **Doorbell device** — optional: select any on/off Indigo device; when it turns on, HomeKit fires a doorbell notification with live video
   - **Motion sensor** — BI cameras automatically register as HomeKit motion sensors
6. Click **Save Device** then **Save** in the dialog

---

## Blue Iris Stream Settings

HKLS uses **Stream 2** from Blue Iris for HomeKit. Optimal settings for zero-transcoding passthrough:

![Blue Iris Streaming 2 Settings](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/BlueIris-Streaming2-Settings.png?raw=true)

### Recommended Profile 2 settings:
- **Codec:** H.264 (Constrained Baseline, level ≤ 4.0 ideal)
- **Pixel format:** yuv420p
- **GOP:** Keep low (≤ 2 seconds between keyframes)

> **Tip:** After changing Blue Iris stream settings, run **Plugins → HomeKitLink Siri → Check or Update Camera Streams for Compatibility** to update how HKLS processes the stream.

---

## Camera Stream Intelligence (v0.7.25+)

HKLS now includes automatic stream compatibility checking via `ffprobe`:

### How It Works
At startup, HKLS silently analyses every configured camera stream. Based on the results:
- **H.264 + yuv420p + compatible GOP** → stream is passed through unchanged (zero transcoding, lowest CPU)
- **Incompatible codec / pixel format / GOP** → HKLS auto-transcodes the stream to H.264 for HomeKit

### Check Camera Streams Manually

Run: **Plugins → HomeKitLink Siri → Check or Update Camera Streams for Compatibility**

Example output:
```
HomeKitLink Siri   [Deck Camera]   Video: codec=h264  profile=Constrained Baseline  pix_fmt=yuv420p  2688x1520 @ 15.0 fps
HomeKitLink Siri   [Deck Camera]   GOP: 15 frames (1.1s between keyframes)
HomeKitLink Siri   [Deck Camera]   ✓ H.264 + yuv420p — safe for copy/passthrough.
HomeKitLink Siri   [Deck Camera]   Config: video_codec=copy — passthrough active. Good.
HomeKitLink Siri   [Deck Camera]   Audio: codec=aac  rate=64000  channels=1
HomeKitLink Siri   [Deck Camera]   Config encoder: libopus — will transcode from aac.
```

> **Run this after any Blue Iris stream setting change.** It updates HKLS's internal decision on whether to passthrough or transcode.

---

## Opus Audio (v0.7.10+)

### The Problem
FFmpeg uses 48 kHz timestamps for Opus audio (per RFC 7587), but HomeKit expects the negotiated clock rate (e.g. 16 kHz). This mismatch caused silent or distorted audio.

### The Solution — Audio Proxy
HKLS includes a native **homekit_audio_proxy** — a subprocess-based RTP/SRTP audio proxy that:
1. Receives plain RTP from FFmpeg
2. Converts timestamps from 48 kHz to HomeKit's expected rate
3. Encrypts with SRTP (AES_CM_128_HMAC_SHA1_80)
4. Forwards to the HomeKit client

The result is **near-perfect audio quality** in the Home app.

### Blue Iris Cameras
BI cameras default to **libopus** for audio encoding. After enabling this feature, cameras must be **removed from Home and re-added** so the Home app can reassess the audio stream.

### SecuritySpy Cameras
SecuritySpy cameras gain the same libopus audio proxy support.

---

## Doorbell Integration

Any HKLS camera can have a **Doorbell** device associated with it:

- Select any on/off Indigo device as the doorbell trigger
- When that device turns **on**, HomeKit fires a doorbell notification
- The notification shows the **live camera stream** — tap to view the feed
- Works great with smart doorbells, button devices, or motion-triggered relays

---

## Camera Performance Tuning

Configure camera performance in **Plugin Config** (Plugins → HomeKitLink Siri → Configure…):

| Setting | Default | Effect |
|---|---|---|
| Camera Max Refresh Time | 30s | Max rate at which HKLS delivers images to Home. Lower = more CPU/network |
| Passive Camera Update Time | 1 hour | How often HKLS refreshes the image buffer when Home is not watching |
| Image Width | — | Width of snapshot images |

---

## Debugging Camera Issues

### Rerun FFmpeg Command for Logging

**Plugins → HomeKitLink Siri → Rerun Ffmpeg Call for Logging**

Replays the last camera stream command and logs the full FFmpeg output. Use this to identify:
- RTSP URL problems
- FFmpeg codec errors
- Authentication failures

### Debug Level 7

Enable **Debug 7 — Camera** in Plugin Config for verbose camera stream logging.

### Common Camera Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Black screen in Home | RTSP URL unreachable | Check BI/SS is running; test URL in VLC |
| Audio missing or distorted | Old camera not re-added after Opus update | Remove camera from Home, re-add via QR code |
| High CPU usage | Stream requires transcoding | Fix BI Profile 2 settings for H.264 passthrough |
| Camera not appearing in list | BI/SS plugin not installed or camera not configured | Install respective plugin, configure cameras |
| Stream check shows "borderline GOP" | GOP too large | Reduce keyframe interval in BI Profile 2 |

---

→ [Plugin Menu Items](Plugin-Menu-Items) — all menu tools explained
