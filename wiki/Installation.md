![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Installation

---

## Requirements

| Requirement | Detail |
|---|---|
| **Indigo version** | 2022.1 or later (Python 3 required) |
| **macOS** | 10.15 Catalina or later; macOS Sequoia 15.x has extra [Local Network Access](Troubleshooting#macos-sequoia-local-network-access) requirements |
| **iOS / iPadOS** | 16.0 or later recommended for Home app |
| **Apple Home Hub** | Strongly recommended (HomePod or Apple TV) for reliable remote access and persistent connections |

---

## Installing the Plugin

### From the Indigo Plugin Store

1. Open Indigo → **Plugins → Manage Plugins…**
2. Search for **HomeKitLink Siri**
3. Click **Install**
4. Indigo will download and install the plugin automatically

### Manual Installation (GitHub)

1. Go to the [GitHub Releases page](https://github.com/Ghawken/HomeKitLink-Siri/releases)
2. Download the latest **`HomeKitLink-Siri.indigoPlugin`** file
3. Double-click the `.indigoPlugin` file — Indigo opens an install prompt
4. Click **Install and Enable**

---

## First-Run Setup

When the plugin starts for the first time it will automatically install its Python dependencies (`pyhap`, `cryptography`, `zeroconf`, `orjson`, and others) via pip. You will see activity in the Indigo log during this process — **this is normal** and only happens once per Python environment.

### Verify Installation

Check the Indigo log for:

```
HomeKitLink Siri    Plugin starting...
HomeKitLink Siri    All dependencies installed successfully
```

If you see dependency errors, try:

1. **Plugins → HomeKitLink Siri → Restart HomeKit** from the plugin menu
2. If still failing, check [Troubleshooting](Troubleshooting#dependency-installation-failures)

---

## macOS Sequoia (15.x) — Local Network Access

macOS Sequoia introduced a mandatory **Local Network Access** permission for applications that use mDNS multicast (which HKLS requires for HomeKit bridge discovery).

**You must grant this permission to IndigoPluginHost3 (and Indigo Server):**

1. Open **System Settings → Privacy & Security → Local Network**
2. Find **IndigoPluginHost3** in the list — enable the toggle
3. Also enable **Indigo** (the server application) if listed
4. If neither appears, restart the plugin — macOS should prompt automatically

> **Run Troubleshoot 2 (Network Trouble Shooting)** from the plugin menu to verify Local Network Access is working. It performs a definitive multicast send test that confirms LNA is enabled.

---

## Uninstalling

1. **Remove all HKLS bridges from the iOS Home app first** — open the Home app, find each bridge and remove it
2. In Indigo: delete all HomeKitLink Bridge devices
3. Disable the plugin: **Plugins → HomeKitLink Siri → Enable/Disable**
4. Remove via **Plugins → Manage Plugins…**

---

## Next Steps

→ [Quick Start](Quick-Start) — create your first bridge and publish your first device
