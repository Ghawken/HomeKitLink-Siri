![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# FAQ — Frequently Asked Questions

---

## General

### What does HomeKitLink Siri do?

HKLS creates one or more **HomeKit Bridges** inside Indigo. Each bridge exposes up to 95 Indigo devices to Apple HomeKit — lights, sensors, cameras, thermostats, locks, and more. Once paired, you control devices through the iOS Home app, Siri, and HomeKit automations.

### Do I need Homebridge?

No. HKLS is a native Indigo plugin with a built-in HomeKit implementation. If you have unsupported hardware in Indigo but want it in HomeKit, you could run a separate Homebridge instance — but for native Indigo devices, HKLS is the recommended approach.

### Does it work with Siri?

Yes. Once a bridge is paired in the Home app, all your devices are available to Siri by name, room, or group.

### Do I need a Home Hub?

A Home Hub (HomePod, HomePod mini, or Apple TV) is **strongly recommended**:
- Enables remote access when away from home
- Automations run reliably even without your iPhone present
- Maintains persistent, stable connections to bridges (without a hub, iOS 16.4+ may close and reopen connections)

---

## Setup

### How many devices can I have per bridge?

Up to **95 devices** per HomeKitLink Bridge device in Indigo.

### How many bridges can I create?

**Unlimited.** Create as many as needed to accommodate all your devices, or to organise them by room or device type.

### Can one Indigo device appear in two bridges?

No — each Indigo device can only be published to **one** HKLS bridge at a time.

### Can I have the same physical device appear twice in HomeKit under different names?

Yes, but you need two separate Indigo devices. Use the **Masquerade** plugin or create an Indigo **Virtual Device** that mirrors the original. Publish each to the same or different bridge.

### What happens if I delete a bridge device?

Devices published to that bridge become "orphaned." Run **Plugins → HomeKitLink Siri → Unlink any Orphaned Devices** to clean up the references. You can then re-publish those devices to a new bridge.

---

## Devices & Types

### What HomeKit device types does HKLS support?

Full list on the [Supported Devices](Supported-Devices) page. Highlights: lights (colour/dimmer/switch), fans, switches, outlets, all sensor types, blinds, windows, thermostats, locks, garage doors, cameras, security systems, valves, action groups.

### Can I assign any HomeKit type to any Indigo device?

With **Show All Options** enabled — yes. Without it, HKLS restricts choices to sensible options for the device category. Use Show All with care; an incompatible type can cause the bridge to fail.

### Why is my temperature sensor showing 0?

The device state being used contains a string (e.g. `"22.1°C"`) instead of a plain number (`22.1`). Change the mapped state in the bridge config to one that returns a numeric value only.

### My device disappeared from HomeKit after I changed its type. What happened?

When you change a device from one HomeKit type to another, the old accessory must be explicitly removed first. See [Setup & Configuration — Changing a Device's HomeKit Type](Setup-and-Configuration#changing-a-devices-homekit-type) for the correct procedure.

---

## Cameras

### Which camera systems does HKLS support?

**Blue Iris** (via the Blue Iris Indigo plugin) and **SecuritySpy** (via FlyingDiver's SecuritySpy plugin). Other cameras are not officially supported.

### Why is my camera audio missing or choppy after the 0.7.10 upgrade?

The new Opus audio proxy requires that cameras be **removed from the Home app and re-added**. This triggers the Home app to renegotiate the audio stream with the correct parameters.

### What settings should I use in Blue Iris for best performance?

Use Profile 2 with H.264 (Constrained Baseline), yuv420p, and a low keyframe interval (GOP). See [Camera Setup — Blue Iris Stream Settings](Camera-Setup#blue-iris-stream-settings) for the recommended settings screenshot.

### What is the "Check or Update Camera Streams" menu item for?

It runs `ffprobe` against all configured camera RTSP streams and tells you whether each stream can be passed through directly (zero transcoding) or needs transcoding. Run it whenever you change Blue Iris stream settings.

---

## Connectivity & Discovery

### My bridge isn't appearing in the Home app. What do I do?

Run all three Troubleshoot menu items first:
1. **Troubleshoot 1** — Support Information
2. **Troubleshoot 2** — Network Trouble Shooting
3. **Troubleshoot 3** — mDNS Troubleshooting

See [Troubleshooting](Troubleshooting) for the step-by-step guide.

### I'm on macOS Sequoia (15.x) and my bridge is not discoverable.

macOS Sequoia requires **Local Network Access** permission for HKLS. Go to **System Settings → Privacy & Security → Local Network** and enable the toggle for **IndigoPluginHost3**. Run **Troubleshoot 2** to confirm it's working.

### The bridge shows "This accessory needs to be reset" in the Home app.

1. Delete the bridge from the Home app
2. Run **Plugins → HomeKitLink Siri → Reset Accessory / Bridge**
3. Restart the plugin
4. Re-add with the QR code

### Can HKLS work with multiple network interfaces (Ethernet + Wi-Fi, VPN, etc.)?

Yes — HKLS 0.7.40+ binds to all IPv4 interfaces by default. If you need to specify a particular interface, use the **HAP Server IP Address** and **mDNS Interfaces** settings in Plugin Config. See [Advanced Configuration](Advanced-Configuration).

---

## Troubleshooting & Support

### Where do I get support?

- **Indigo Forum:** [HomeKitLink Siri forum](https://forums.indigodomo.com/viewforum.php?f=366)
- **GitHub Issues:** [github.com/Ghawken/HomeKitLink-Siri/issues](https://github.com/Ghawken/HomeKitLink-Siri/issues)

### What should I include in a forum post?

Always include the output from all three Troubleshoot menu items. Without this, diagnosing issues is much harder. See [Troubleshooting — Posting on the Forum](Troubleshooting#posting-on-the-forum).

### What's different from the old HomeKit-Bridge plugin?

HKLS is a completely independent implementation. The underlying HomeKit protocol handling, architecture, and configuration are entirely different from the earlier plugin. Feature comparisons or requests prefaced with "HomeKit-Bridge did this" have lower priority in development since the implementations share nothing in common.

---

## Limitations

### Can I publish more than 95 devices?

Not per bridge. Create additional bridges to accommodate more devices. The number of bridges is unlimited.

### Does HKLS support [some obscure HomeKit feature]?

Feature requests and compatibility additions are welcome on the [GitHub Issues page](https://github.com/Ghawken/HomeKitLink-Siri/issues). The development priority focuses on native Indigo devices first. For plugin-specific third-party devices (Samsung TVs via plugins, etc.), running a separate Homebridge instance is recommended.

### Why are security systems only partially supported?

Testing security systems requires the actual hardware to trigger states and test responses. If you have a supported alarm system and can test, reports and details are very welcome on the forum.
