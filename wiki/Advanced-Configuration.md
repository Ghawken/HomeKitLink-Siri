![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Advanced Configuration

---

## Advanced mDNS Options

![Advanced Options](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/AdvancedOptions.png?raw=true)

> **⚠️ Use these settings with caution.** Incorrect mDNS configuration can make bridges undiscoverable. Only change these if the standard configuration isn't working and you understand what each setting does. Run [Troubleshoot 3](Plugin-Menu-Items#ℹ️-troubleshoot-3--support-mdns-troubleshooting) before and after making changes.

### mDNS IP Version

Controls which IP protocol version mDNS/Bonjour uses for bridge advertisements.

| Value | Behaviour |
|---|---|
| **IPVersion.V4Only** *(default)* | Advertise on IPv4 only. Recommended for most setups — the HAP server is IPv4-only |
| IPVersion.All | Advertise on both IPv4 and IPv6 |
| IPVersion.V6Only | Advertise on IPv6 only — rarely useful |

> **Note:** If you specify a list of IPv4 interfaces AND select IPVersion.All, zeroconf may fail when it tries IPv6. Use `IPVersion.V4Only` when providing explicit interface addresses.

### mDNS Interfaces

A comma-separated list of IP addresses that HKLS should bind mDNS to.

- **Leave empty** — HKLS auto-derives the interface list from the HAP server IP address
- **Single address** — e.g. `192.168.1.6` — bind to one specific interface
- **Multiple addresses** — e.g. `192.168.1.6,10.0.0.5` — bind to multiple interfaces (use with `IPVersion.V4Only`)

**When to use:** If your Mac has multiple network interfaces (ethernet + Wi-Fi, VPN, etc.) and HomeKit bridges are being advertised on the wrong interface, specify the correct one here.

### mDNS Use Apple AWDL

Apple Wireless Direct Link — peer-to-peer connectivity. Default: **disabled**. Enable only if you're experimenting with AWDL-based HomeKit discovery; this is not needed for normal HomeKit operation.

---

## HAP Server Options

### HomeKit Server IP Address (HAPServerIPAddress)

Forces HKLS to use a specific IP address for the HAP (HomeKit Accessory Protocol) TCP server. This is distinct from the mDNS interface setting.

- Must be an IP address of the Mac running Indigo
- Leave empty for automatic selection
- Use when the wrong network interface is being chosen (e.g. VPN tunnel being preferred over LAN)

**Auto-derive:** When `HAPServerIPAddress` is set but `mDNSInterfaces` is empty, the mDNS interface list is automatically derived as `[HAPServerIPAddress]` — meaning both settings track together.

### Starting Port Number

Default: **51840**

Each HKLS bridge uses a sequential port number (Bridge 0 = 51840, Bridge 1 = 51841, etc.). Change the base port if there are conflicts with other software.

HKLS checks whether each port is in use at startup and will skip occupied ports.

---

## Debug Options Deep Dive

All debug options are in **Plugins → HomeKitLink Siri → Configure…**

| Debug Level | What it logs | When to use |
|---|---|---|
| **1** — HomeKit Callbacks | Every HAP callback (get/set from HomeKit) | When HomeKit isn't receiving correct values |
| **2** — Device Update Reporting | Every Indigo → HomeKit state push | When device states seem stale in HomeKit |
| **3** — HomeKit Library (Verbose!) | Full `pyhap` library internals | HAP protocol debugging — very noisy |
| **4** — Getter Callback | HomeKit property reads | When HomeKit is reading wrong values |
| **5** — Setter Callback | HomeKit property writes | When HomeKit control commands aren't working |
| **6** — HomeKit Devices | Device-level state tracing | Per-device HomeKit interaction |
| **7** — Camera | Camera stream, FFmpeg, SRTP | Camera stream not working |
| **8** — Device Selection | Device list/filter generation | Debug config dialog device list |
| **9** — IID Manager | HomeKit IID allocation | Debugging characteristic ID conflicts |
| **10** — mDNS (File Only!) | Zeroconf/Bonjour detailed logs | Written to plugin log file — not Indigo log |
| **11** — Actions | Action group triggering | Action groups not triggering in HomeKit |

### Debug Single Device

The **Debug Device** menu in Plugin Config lets you select one specific Indigo device to trace. When a device is selected:
- Only that device's HomeKit callbacks are verbosely logged
- Much less noise than enabling debug for all devices
- Ideal for narrowing down issues with a single accessory

---

## Python 3.13 Compatibility (v0.8.05+)

HKLS 0.8.05 was updated for full Python 3.13 compatibility:

- Removed `async_timeout` dependency — uses Python 3.11+ built-in `asyncio.timeout`
- Updated library versions: `cryptography` 41→46, `orjson` 3.8→3.11, `h11` 0.14→0.16, `zeroconf` 0.131→0.148, `chacha20poly1305-reuseable` 0.12→0.13
- Removed `slugify` and `aiofiles` dependencies
- Added `cffi`, `pycparser`, `ifaddr` as explicit dependencies
- Fixed pip install success detection (glob matching for Python-versioned filenames)

---

## Multiple Network Interfaces

If your Mac has multiple network interfaces active (common with VPN, Ethernet + Wi-Fi, or USB network adapters):

1. Run **Troubleshoot 2** — it shows which IP HKLS is auto-detecting and which ports are bound
2. Set **HAP Server IP Address** to the specific interface HomeKit clients can reach
3. Set **mDNS Interfaces** to the same IP address
4. Use **IPVersion.V4Only**

> HKLS 0.7.40+ binds to all IPv4 interfaces by default, which should resolve most multi-NIC issues automatically.

---

## Home App Without a Home Hub

After iOS/iPadOS 16.4, Apple changed HomeKit connection architecture. Without a Home Hub (HomePod mini, HomePod, or Apple TV):

- The Home app may close and reopen connections more aggressively
- Bridges remain functional but may show a brief delay when reconnecting
- **A Home Hub is strongly recommended** for stable, persistent HomeKit connections

With a Home Hub:
- Remote access works
- Automations run even when you're away
- Connections are persistent and fast

---

## mDNS Useful External Tools

| Tool | Platform | Use |
|---|---|---|
| [Discovery - DNS-SD Browser](https://apps.apple.com/us/app/discovery-dns-sd-browser/id1381004916?mt=12) | macOS | Browse all mDNS services on your network — verify bridges are advertising |
| [RouteThis](https://support.lifx.com/en_us/free-network-improvement-tool-routethis-ByvgG_iIu) | iOS/macOS | Network diagnostic tool for multicast/mDNS issues |

---

→ [Changelog](Changelog) — version history
