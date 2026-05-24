![HomeKitLink Siri](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

<p align="center">
  <a href="https://forums.indigodomo.com/viewforum.php?f=366"><img src="https://img.shields.io/badge/Forum-Indigo%20Domotics-blue?style=flat-square" alt="Forum"></a>
  <a href="https://github.com/Ghawken/HomeKitLink-Siri/releases"><img src="https://img.shields.io/github/v/release/Ghawken/HomeKitLink-Siri?style=flat-square&label=Latest%20Release" alt="Latest Release"></a>
  <a href="https://github.com/Ghawken/HomeKitLink-Siri/wiki"><img src="https://img.shields.io/badge/Wiki-Documentation-green?style=flat-square" alt="Wiki"></a>
</p>

# HomeKitLink Siri

**Native HomeKit integration for [Indigo](https://www.indigodomo.com/) home automation.**

HomeKitLink Siri (HKLS) is an Indigo plugin that creates HomeKit Bridges — exposing your Indigo devices to Apple HomeKit and Siri. No Homebridge. No external servers. Everything runs inside Indigo.

> **Version 0.8.05** &nbsp;|&nbsp; Requires Indigo 2022.1+ (Python 3)

---

## Features

- 🏠 **HomeKit Bridges** — create unlimited bridges, up to 95 devices each
- 💡 **Lights** — colour, colour temperature, dimmer, switch
- 🌡️ **Sensors** — temperature, humidity, motion, occupancy, contact, luminance, smoke, CO, leak
- 📷 **Cameras** — BlueIris & SecuritySpy with live video, Opus audio, motion detection, doorbell
- 🔒 **Locks, Garage Doors, Blinds, Windows**
- 🌀 **Fans** (simple & speed-controlled), **Thermostats**, **Valves**, **Security Systems**
- 🎙️ **Siri** control of everything once paired
- 🔍 **Built-in diagnostic tools** — network troubleshooter, mDNS checker, support log generator

---

## Quick Start

1. Install the plugin from the Indigo Plugin Store, or [download from Releases](https://github.com/Ghawken/HomeKitLink-Siri/releases)
2. Create a **HomeKitLink Bridge** device in Indigo
3. Add your devices, check Publish, click Save Device → Save
4. Open the iOS Home app → Add Accessory → scan the QR code
5. Done — control with Siri immediately

→ **[Full Quick Start Guide](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Quick-Start)**

---

## Documentation

The complete documentation is in the **[Wiki](https://github.com/Ghawken/HomeKitLink-Siri/wiki)**:

| | |
|---|---|
| [Installation](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Installation) | Requirements, install, first run |
| [Quick Start](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Quick-Start) | Bridge setup, pairing, Siri |
| [Setup & Configuration](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Setup-and-Configuration) | Device config, Plugin Config, limits |
| [Supported Devices](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Supported-Devices) | All HomeKit device types |
| [Camera Setup](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Camera-Setup) | BlueIris, SecuritySpy, Opus audio |
| [Plugin Menu Items](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Plugin-Menu-Items) | All menu tools explained |
| [Troubleshooting](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Troubleshooting) | Common issues & fixes |
| [Advanced Configuration](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Advanced-Configuration) | mDNS, networking, debug options |
| [Changelog](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Changelog) | Full version history |
| [FAQ](https://github.com/Ghawken/HomeKitLink-Siri/wiki/FAQ) | Common questions |

---

## ⚠️ Having Issues? Run These First

Before posting on the forum, run the three built-in diagnostic tools:

**Plugins → HomeKitLink Siri →**
1. **ℹ️ Troubleshoot 1 — Support Information For Forum Posting**
2. **ℹ️ Troubleshoot 2 — Network Trouble Shooting**
3. **ℹ️ Troubleshoot 3 — Support mDNS Troubleshooting**

Copy the Indigo log output and include it in your forum post. These tools diagnose the vast majority of connectivity and discovery issues.

→ [Troubleshooting Guide](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Troubleshooting)

---

## Screenshots

<table>
<tr>
<td><img src="https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/DeviceConfig1.png?raw=true" alt="Device Config" width="320"/></td>
<td><img src="https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/MenuItems_new.png?raw=true" alt="Menu Items" width="320"/></td>
</tr>
<tr>
<td align="center"><em>Bridge device configuration</em></td>
<td align="center"><em>Plugin menu items</em></td>
</tr>
<tr>
<td><img src="https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/DeviceConfig3.png?raw=true" alt="Device List" width="320"/></td>
<td><img src="https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/AdvancedOptions.png?raw=true" alt="Advanced Options" width="320"/></td>
</tr>
<tr>
<td align="center"><em>Published device list (greyed = other bridge)</em></td>
<td align="center"><em>Advanced mDNS options</em></td>
</tr>
</table>

---

## Key Limitations

- Each Indigo device can only be published to **one** bridge at a time
- **95 devices maximum** per bridge (create more bridges as needed)
- Cameras: **Blue Iris** and **SecuritySpy** supported; other camera systems are not

---

## Support

- **Forum:** [HomeKitLink Siri — Indigo Forums](https://forums.indigodomo.com/viewforum.php?f=366)
- **Issues:** [GitHub Issues](https://github.com/Ghawken/HomeKitLink-Siri/issues)
- **Wiki:** [Full Documentation](https://github.com/Ghawken/HomeKitLink-Siri/wiki)

---

## Changelog

See the [full Changelog](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Changelog) in the wiki.

### 0.8.05 — Latest
- **Camera Audio:** Opus SRTP proxy — near-perfect HomeKit audio for BlueIris & SecuritySpy cameras
- **Camera Intelligence:** `ffprobe`-based stream analysis — auto passthrough or transcode per camera
- **mDNS Refactor:** IPv4-only default, fixed interface/address conflation, auto-derive interface from server IP
- **Diagnostic Tools:** New "Network Trouble Shooting" and "mDNS Troubleshooting" menu items
- **Python 3.13:** Full compatibility — updated all libraries, removed deprecated dependencies
- Bug fixes for interfaces, image snapshots, multi-NIC discovery

### 0.7.x Series
- Opus audio proxy for BlueIris and SecuritySpy cameras
- Blue Iris stream intelligence with ffprobe
- SecuritySpy plugin support (motion events, doorbell)
- mDNS IPv4-only default, multi-NIC binding improvements
- Support information and logging menu improvements

### Earlier versions
See [Changelog](https://github.com/Ghawken/HomeKitLink-Siri/wiki/Changelog) for complete history back to 0.0.4.
