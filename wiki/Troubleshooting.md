![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Troubleshooting

---

## ⭐ Step One — Always Run These Three First

> **These diagnostic tools solve the vast majority of HomeKitLink Siri issues.**  
> **Run them before anything else, and before posting on the forum.**

### 1️⃣ Troubleshoot 1 — Support Information

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 1 Support Information For Forum Posting**

Captures your complete HKLS configuration, bridge status, device publication list, and network settings. **Copy this output and include it in every forum support post.**

---

### 2️⃣ Troubleshoot 2 — Network Trouble Shooting

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 2 Network Trouble Shooting**

Performs a comprehensive network diagnostic — Local Network Access, multicast, firewall, bridge ports, DNS. The output tells you exactly what is and isn't working.

---

### 3️⃣ Troubleshoot 3 — mDNS Troubleshooting

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 3 Support mDNS Troubleshooting**

Checks mDNS/Bonjour health — whether bridges are advertising correctly, interface binding, Bonjour service status. Essential for "bridge not visible" problems.

---

See [Plugin Menu Items](Plugin-Menu-Items#troubleshoot-items) for full details on what each tool checks.

---

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## Bridge Not Visible in Home App

This is the most common issue. Work through these steps in order:

### 1. Run Troubleshoot 2 & 3 (above)

The output will identify the problem in most cases.

### 2. Check Network Basics

- Is the Mac running Indigo on the **same Wi-Fi network** as the iPhone?
- Is the Mac accessible and not behind a firewall?
- Try adding the bridge from a **different iOS device** — if it works there, the issue is with that specific iPhone

### 3. macOS Sequoia — Local Network Access {#macos-sequoia-local-network-access}

macOS Sequoia (15.x+) requires **Local Network Access** permission for mDNS to work:

1. Open **System Settings → Privacy & Security → Local Network**
2. Enable the toggle for **IndigoPluginHost3**
3. Also enable **Indigo** (the server app) if listed
4. If neither appears: restart the HKLS plugin — macOS will prompt for permission

> Troubleshoot 2 performs a **definitive multicast send test** that confirms whether LNA is blocked. Look for:
> ```
> ✅ Successfully sent multicast packet to 224.0.0.251:5353 — Local Network Access is ENABLED.
> ```
> vs.
> ```
> ❌ Failed to send multicast packet — Local Network Access may be BLOCKED.
> ```

### 4. Reset Bridge Encryption

HomeKit encryption state can sometimes get corrupted. If the bridge previously worked but stopped being discoverable:

1. Remove the bridge from the Home app
2. Run **Plugins → HomeKitLink Siri → Reset Accessory / Bridge**
3. Restart the plugin
4. Re-add with the QR code

### 5. Wi-Fi Network Reset (iOS)

On your iPhone:
1. Settings → Wi-Fi → your network → **Forget This Network**
2. Reconnect to the Wi-Fi
3. Try adding the bridge again

### 6. No Published Devices — Test the Bridge

A bridge with **no published devices** running successfully confirms the issue is network/discovery, not a device configuration problem. Try:
1. Remove all devices from a bridge (uncheck Publish, Save each)
2. Save the dialog — restart the bridge
3. Try to see the empty bridge in the Home app

If the empty bridge is visible, the problem is with a specific device configuration.

---

## Bridge Stops Responding After Device Type Change

**Cause:** A device was changed from one HomeKit type to another without following the correct procedure.

**Fix:**
1. Uncheck **Publish** for the problem device → **Save Device**
2. **Save** the dialog (restart the bridge)
3. Confirm the old device type has disappeared in the Home app
4. Re-add the device with the new type

See [Setup & Configuration — Changing a Device's HomeKit Type](Setup-and-Configuration#changing-a-devices-homekit-type) for the full procedure.

---

## Device Shows Wrong Value / Shows Zero

**Cause:** The Indigo device state being used contains a type the sensor doesn't expect.

**Common example:** Temperature sensor state contains `"22.1°C"` (string with units) instead of `22.1` (plain number).

**Fix:**
1. Open the bridge config, select the device
2. Check which state is mapped — the config shows the current value
3. Select a different state that contains a plain number
4. If no suitable state exists, the device may need to be pre-processed (e.g. via an Indigo variable and virtual device)

---

## Bridge Causes "Needs to be Reset" in Home App

**Cause:** The bridge was added to the Home app and then something changed the bridge's security keys without re-pairing.

**Fix:**
1. Delete the bridge from the **Home app** first
2. **Plugins → HomeKitLink Siri → Reset Accessory / Bridge** — select the bridge
3. Run **Plugins → HomeKitLink Siri → Restart HomeKit**
4. Re-add via QR code

---

## Dependency Installation Failures

If the plugin log shows pip install errors at startup:

1. Check the Indigo log for the specific package that failed
2. Try **Plugins → HomeKitLink Siri → Restart HomeKit**
3. Check macOS has network access (pip downloads from PyPI)
4. If a specific package repeatedly fails, post on the forum with the full error output

---

## mDNS / Bonjour Issues

### Tools to Help

- [Troubleshoot 3](#3️⃣-troubleshoot-3--mdns-troubleshooting) — built-in mDNS diagnostic
- [Discovery - DNS-SD Browser](https://apps.apple.com/us/app/discovery-dns-sd-browser/id1381004916?mt=12) (macOS) — see mDNS advertisements on your network
- [RouteThis](https://support.lifx.com/en_us/free-network-improvement-tool-routethis-ByvgG_iIu) — network diagnostic tool

### Advanced mDNS Options

See [Advanced Configuration](Advanced-Configuration#advanced-mdns-options) for interface binding, IP version selection, and AWDL settings.

---

## Camera Issues

See the Camera Setup troubleshooting section: [Camera Setup — Common Camera Issues](Camera-Setup#common-camera-issues)

---

## Orphaned Devices

If Show Device Publications shows devices in **red** (bridge deleted):

**Plugins → HomeKitLink Siri → Unlink any Orphaned Devices**

This clears the bridge reference so the devices can be re-published to a new bridge.

---

## Posting on the Forum

The [HomeKitLink Siri forum](https://forums.indigodomo.com/viewforum.php?f=366) is the best place for support. To get the fastest help:

1. ✅ Run all three Troubleshoot menu items
2. ✅ Copy the **complete** Indigo log output from each tool
3. ✅ Describe what you expected vs. what happened
4. ✅ Include your Indigo version, macOS version, and plugin version
5. ❌ Don't post partial logs — include everything from the troubleshoot tools

> **The troubleshoot tools give forum helpers everything they need.** Without this output, diagnosing your issue is much harder and slower.

---

→ [Advanced Configuration](Advanced-Configuration) — mDNS, networking, debug deep-dive
