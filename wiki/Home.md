![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# HomeKitLink Siri — Plugin Wiki

**HomeKitLink Siri (HKLS)** is an [Indigo](https://www.indigodomo.com/) plugin that creates HomeKit Bridges, exposing your Indigo devices to Apple HomeKit and Siri control — all natively, with no Homebridge or external server required.

> **Current version:** `0.8.45` (preliminary release) &nbsp;|&nbsp; **Requires:** Indigo 2025.1+ (Python 3)  
> **Forum:** [HomeKitLink Siri on Indigo Forums](https://forums.indigodomo.com/viewforum.php?f=366)  
> **GitHub:** [Ghawken/HomeKitLink-Siri](https://github.com/Ghawken/HomeKitLink-Siri)

### What's new since 0.8.05

| | |
|---|---|
| ⚠️ **Bridges keep their port** (0.8.40) | **Important if you run more than one bridge.** Adding a bridge used to move the others to new ports, and home hubs that remembered the old ports showed whole bridges as **No Response**. Ports are now saved per bridge. → [Troubleshooting](Troubleshooting#no-response-on-a-whole-bridge-everything-works-from-indigo) |
| 📷 **Improved live view** (0.8.44) | On by default: video sent from the port HomeKit expects, HomeKit-sized re-encoding, and remote views start at 720p instead of 640×360. Copied (passthrough) streams keep the camera's full picture. → [Camera Setup](Camera-Setup#improved-live-view-v0844) |
| 🔎 **Wrong-bridge warning** (0.8.41) | The log names any Home device that reaches the wrong bridge (an old port), and what to do. **Troubleshoot 4** lists every bridge's port and checks the saved ports. → [Plugin Menu Items](Plugin-Menu-Items#ℹ️-troubleshoot-4--homekit-pairing--security-keys) |
| 🧩 **New HomeKitLink devices** | **HomeKitLink Sensor** (one state of any device as its own HomeKit sensor), **HomeKit Buttons** (Indigo starts Home app automations), **HKSV Recorder**. → [HomeKitLink Devices](HomeKitLink-Devices) |
| 🎥 **HomeKit Secure Video** | Home hubs record a camera's motion and doorbell events to iCloud. → [Camera Setup](Camera-Setup#homekit-secure-video-v0822) |
| 📷 **Cameras** | **UniFi Protect** cameras with two-way audio; **Blue Iris** live views start ~1.7 s sooner (0.8.38); repeated short views from Home widgets logged once (0.8.39). → [Camera Setup](Camera-Setup) |
| 🌡️ **New HomeKit types** | **Heater-Cooler** (AC, with zones such as Actron Que), **Air Quality Sensor**, **Vacuum / Lawn Mower**. → [Supported Devices](Supported-Devices) |
| ⚙️ **Bridge settings** | Search with Find / Clear, proper sorting, new list types, fewer settings stored on your devices. → [Setup & Configuration](Setup-and-Configuration) |

Everything new is opt-in: devices you don't change behave as before. Full detail: [Changelog](Changelog).

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## Quick Navigation

| | |
|---|---|
| 🚀 [Installation](Installation) | Get HKLS installed in Indigo |
| ⚡ [Quick Start](Quick-Start) | Add your first bridge & device |
| ⚙️ [Setup & Configuration](Setup-and-Configuration) | Full device setup guide |
| 📱 [Supported Devices](Supported-Devices) | All supported HomeKit device types |
| 🧩 [HomeKitLink Devices](HomeKitLink-Devices) | HomeKitLink Sensor, HomeKit Buttons and HKSV Recorder |
| 🎥 [Camera Setup](Camera-Setup) | BlueIris, SecuritySpy & UniFi Protect configuration |
| 🔧 [Plugin Menu Items](Plugin-Menu-Items) | All plugin menu actions explained |
| 🆘 [Troubleshooting](Troubleshooting) | **Run menu items 1, 2 & 3 first!** |
| 🔬 [Advanced Configuration](Advanced-Configuration) | mDNS, networking & debug options |
| 📋 [Changelog](Changelog) | Version history |
| ❓ [FAQ](FAQ) | Frequently asked questions |

---

## What is HomeKitLink Siri?

HKLS lets you publish any Indigo device into Apple's Home ecosystem. You create one or more **HomeKitLink Bridge** devices inside Indigo. Each bridge acts as a HomeKit accessory bridge — you pair it once with a QR code in the iOS Home app, and every Indigo device you add to it appears automatically in HomeKit.

**Highlights:**
- 🏠 Create **unlimited bridges** (up to 95 devices each)
- 🎛️ Supports lights, fans, switches, sensors, cameras, thermostats, locks, blinds, security systems and more
- 🔒 Device configuration is stored in the Indigo database — migrates with Indigo
- 🎙️ Full **Siri** control once paired
- 📷 Native **BlueIris**, **SecuritySpy** and **UniFi Protect** camera streaming with Opus audio
- 🔍 Built-in **diagnostic tools** — network troubleshooter, mDNS checker, support log

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## ⚠️ Before You Post in the Forum

**Always run the Troubleshoot menu items before posting a support request:**

> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 1 – Support Information For Forum Posting**  
> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 2 – Network Troubleshooting**  
> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 3 – Support mDNS Troubleshooting**  
> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 4 – HomeKit Pairing & Security Keys** (pairing / won't add / No Response on a whole bridge)

Copy the output from the Indigo log and include it in your forum post. These tools diagnose the vast majority of connectivity and discovery issues and give forum helpers everything they need.

See [Plugin Menu Items](Plugin-Menu-Items) and [Troubleshooting](Troubleshooting) for full details.

---

## Architecture Overview

```
Indigo ──► HomeKitLink Siri Plugin
                │
                ├── HomeKitLink Bridge 1 (up to 95 devices)
                │       ├── Light 1
                │       ├── Sensor A
                │       └── Camera 1
                │
                └── HomeKitLink Bridge 2 (up to 95 devices)
                        ├── Thermostat
                        └── Lock
                              │
                   Apple Home App (iOS/macOS)
                   Siri
```

Each bridge runs its own HAP (HomeKit Accessory Protocol) server and mDNS advertisement — fully self-contained inside Indigo.
