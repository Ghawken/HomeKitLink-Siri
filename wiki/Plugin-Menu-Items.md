![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Plugin Menu Items

All HKLS tools are available under **Plugins → HomeKitLink Siri** in the Indigo menu bar.

![Menu Items](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/MenuItems_new.png?raw=true)

---

## ⭐ Troubleshoot Items — Run These First!

> **Before posting any issue on the forum, run all three Troubleshoot items and include the output.**
> These tools diagnose the vast majority of connectivity, mDNS, and network issues automatically.

---

### ℹ️ Troubleshoot 1 — Support Information For Forum Posting

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 1 Support Information For Forum Posting**

Generates a comprehensive summary of your HKLS installation for forum support. Output includes:

- Plugin version and Python version
- All configured bridges and their status
- Published device list
- mDNS / network configuration (IP version, interfaces, listen address, IPv6)
- Active driver count and port assignments
- Any known error conditions

**Use it for:** Any support request. Copy everything from the Indigo log and paste it into your forum post.

---

### ℹ️ Troubleshoot 2 — Network Trouble Shooting

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 2 Network Trouble Shooting**

Performs a comprehensive network diagnostic. Checks:

- **macOS version, Python version, architecture**
- **Apple Local Network Access** — definitive multicast send test (catches LNA blocks that simpler tests miss)
- **mDNS Multicast Group Join** — verifies multicast socket can be opened
- **Outbound UDP connectivity** — tests internet reachability
- **Gateway reachability** — pings your local gateway
- **Firewall status** — checks `socketfilterfw` state, stealth mode, and block-all setting
- **Plugin network configuration** — shows advertised IP, server IP, IP version, interfaces, starting port, active bridges
- **Bridge port checks** — confirms each bridge's TCP port is accepting connections
- **DNS resolution** — checks DNS is working

Example output:
```
HomeKitLink Siri   ✅ Successfully sent multicast packet to 224.0.0.251:5353 via 192.168.1.6
HomeKitLink Siri      Local Network Access is ENABLED.
HomeKitLink Siri   ✅ Port 51840 is accepting connections.
HomeKitLink Siri   ✅ Port 51841 is accepting connections.
```

**Use it when:** Bridge not visible in Home app; HomeKit can't connect; after macOS upgrade.

> **macOS Sequoia (15.x+) users:** Run this to verify Local Network Access is granted to IndigoPluginHost3.

---

### ℹ️ Troubleshoot 3 — Support mDNS Troubleshooting

**Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 3 Support mDNS Troubleshooting**

Focused mDNS/Bonjour diagnostic. Checks:

- Network interfaces and their IP addresses
- Firewall status as it relates to mDNS
- Zeroconf / AsyncZeroconf state
- Bonjour / mDNSResponder service status
- mDNS advertisement records for all active bridges
- Interface binding and IP version settings

**Use it when:** Bridge was previously visible but has disappeared from Home; HomeKit takes a long time to discover bridges; after changing network configuration or IP addresses.

---

![divider](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/divider.gif?raw=true)

## Show Device Publications

**Plugins → HomeKitLink Siri → Show Device Publications**

Lists all Indigo devices currently configured for HomeKit publishing in the Indigo log.

![Log Devices](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/logDevices.png?raw=true)

Status indicators:
- **Normal** — device is published and bridge is running
- **Warning** — bridge is disabled
- **Red** — bridge no longer exists (device is orphaned)

**Use it for:** Auditing which devices are published; identifying orphaned device references.

---

## Identify Devices Running / Not Running

**Plugins → HomeKitLink Siri → Identify Devices Running / Not Running**

Shows which HKLS bridge devices are currently running and which are stopped or disabled.

---

## Toggle Debugging

**Plugins → HomeKitLink Siri → Toggle Debugging**

Quickly toggles the main debug logging level on/off. More granular debug options are in Plugin Config (Configure…).

---

## Restart HomeKit

**Plugins → HomeKitLink Siri → Restart HomeKit**

Stops and restarts all HomeKitLink bridges. Use when:
- A bridge has stopped responding
- You've made configuration changes outside of the device config dialog
- After a network change that may have affected mDNS

---

## Unlink Any Orphaned Devices

**Plugins → HomeKitLink Siri → Unlink any Orphaned Devices**

Removes the HomeKit bridge association for any Indigo device whose bridge device has been deleted from Indigo. Cleans up stale references so those devices can be re-published to a new bridge.

---

## Delete Residual States Files

**Plugins → HomeKitLink Siri → Delete residual States Files**

Deletes any leftover HomeKit state files from deleted or reset bridges. Use when a bridge shows "needs to be reset" in the Home app after being deleted.

---

## Rerun FFmpeg Call for Logging

**Plugins → HomeKitLink Siri → Rerun Ffmpeg Call for logging**

Re-runs the last camera stream FFmpeg command and logs the full output. Useful for diagnosing:
- RTSP stream problems
- FFmpeg codec errors
- Network connectivity to the camera

---

## Check or Update Camera Streams for Compatibility

**Plugins → HomeKitLink Siri → Check or Update Camera Streams for Compatibility**

Runs `ffprobe` against all configured camera RTSP streams and logs compatibility analysis. Determines whether each stream can be passed through unchanged or needs transcoding.

**Run this after:**
- Changing Blue Iris stream / profile settings
- Adding a new camera
- Any change to camera resolution, codec, or frame rate

See [Camera Setup](Camera-Setup#camera-stream-intelligence) for example output.

---

## Debug Log Menu Options

**Plugins → HomeKitLink Siri → Debug Log Menu Options**

Opens a sub-dialog with detailed internal debug logging buttons:

| Button | Logs |
|---|---|
| Debug Log Internal List | HKLS internal device tracking list |
| Debug all Bridges | All bridge objects and their state |
| Debug Log Drivers | All HAP AccessoryDriver instances |
| Debug Log Threads | All running threads and their status |
| Debug Log Device List | Internal device mapping list |
| Debug all Accessories | All registered HomeKit accessories and characteristics |

Use these when investigating internal state issues — particularly useful when a device isn't updating correctly or a bridge appears stuck.

---

## Move Accessories to Another Bridge

**Plugins → HomeKitLink Siri → Move Accessories to another Bridge**

Copies all HomeKit accessories from one bridge to another. Enables recovery when:
- A bridge device was accidentally deleted
- You want to consolidate or reorganise bridges

> **⚠️ This operation carries some risk.** Use with caution and unpair the old bridge from the Home app first.

**Procedure:**
1. Select the **From Bridge** (source)
2. Select the **To Bridge** (destination)
3. Click **Move Accessories**
4. Unpair the old bridge from the Home app

---

## Reset Accessory / Bridge

**Plugins → HomeKitLink Siri → Reset Accessory / Bridge**

![Reset Accessory](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/ResetAccessory.png?raw=true)

Deletes the security keys and pairing information for a selected bridge. Use when:
- A bridge shows "This accessory needs to be reset" in the Home app
- You tried to pair a bridge and it failed or was cancelled, leaving it in a broken state

**Correct procedure:**
1. **Delete the bridge from the Home app first**
2. Select the bridge in this menu
3. Click **Reset Bridge Accessories**
4. Restart the HKLS plugin
5. Re-add the bridge using the QR code

> **⚠️ Do not reset a bridge that is successfully paired in the Home app** — this breaks the existing pairing. You would need to re-pair from scratch.

---

→ [Troubleshooting](Troubleshooting) — full troubleshooting guide
