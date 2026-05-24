![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# HomeKitLink Siri — Plugin Wiki

**HomeKitLink Siri (HKLS)** is an [Indigo](https://www.indigodomo.com/) plugin that creates HomeKit Bridges, exposing your Indigo devices to Apple HomeKit and Siri control — all natively, with no Homebridge or external server required.

> **Current version:** `0.8.05` &nbsp;|&nbsp; **Requires:** Indigo 2022.1+ (Python 3)  
> **Forum:** [HomeKitLink Siri on Indigo Forums](https://forums.indigodomo.com/viewforum.php?f=366)  
> **GitHub:** [Ghawken/HomeKitLink-Siri](https://github.com/Ghawken/HomeKitLink-Siri)

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## Quick Navigation

| | |
|---|---|
| 🚀 [Installation](Installation) | Get HKLS installed in Indigo |
| ⚡ [Quick Start](Quick-Start) | Add your first bridge & device |
| ⚙️ [Setup & Configuration](Setup-and-Configuration) | Full device setup guide |
| 📱 [Supported Devices](Supported-Devices) | All supported HomeKit device types |
| 🎥 [Camera Setup](Camera-Setup) | BlueIris & SecuritySpy configuration |
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
- 📷 Native **BlueIris** and **SecuritySpy** camera streaming with Opus audio
- 🔍 Built-in **diagnostic tools** — network troubleshooter, mDNS checker, support log

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## ⚠️ Before You Post in the Forum

**Always run the three Troubleshoot menu items before posting a support request:**

> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 1 – Support Information For Forum Posting**  
> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 2 – Network Trouble Shooting**  
> **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 3 – Support mDNS Troubleshooting**

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
