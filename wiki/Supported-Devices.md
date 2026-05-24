![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Supported Devices

HKLS supports a wide range of HomeKit accessory types. Everything is user-selectable — with **Show All Options** enabled you can technically assign any HomeKit type to any Indigo device, though sensible defaults are pre-selected for you.

---

## Lights

### Lightbulb

**Best choice for all light devices.**

HKLS automatically detects the correct subtype:

| Subtype | Triggered by |
|---|---|
| **Colour bulb** | Device supports RGB / Hue |
| **Colour temperature bulb** | Device supports colour temperature |
| **Dimmable bulb** | Device is a dimmer |
| **Switch bulb** | Simple on/off only |

> Use **Lightbulb_switch** if you want a simple on/off switch in HomeKit even when the physical device supports dimming.

Within the Home app, lights can be grouped into a single accessory tile.

---

## Fans

### Fan (Simple)

For a basic on/off fan — no speed control.

### Fan V2

For fans with speed control. HKLS auto-selects Fan V2 if the Indigo device is a **Speed Control** device or has a brightness/level state.

> **Tip:** Any switch can be displayed as a Fan icon in the Home app without changing the device type — just tap the icon in Home and change the appearance.

---

## Switch / Outlet

**Simple on/off device.** Works with any Indigo relay device.

- **Action Groups** default to the Switch type
- Within HomeKit, a Switch can be displayed as a **Switch**, **Fan**, or **Outlet** — change the icon in the Home app without reconfiguring HKLS

---

## Sensors

All sensors follow the same pattern: HKLS reads a selected **device state** and maps it to the HomeKit sensor value. The state is chosen when you configure the device.

> **State requirements:**
> - On/Off sensors: state must be `true`/`false`
> - Numeric sensors (temperature, humidity, luminance): state must be a **plain number** — no units suffix

### Motion Sensor
Triggers HomeKit automations and notifications when motion is detected.

### Occupancy Sensor
Reports presence/absence. Verified working with the **Occupatum** plugin and any true/false on/off state device.

### Contact Sensor
Reports open/closed state — doors, windows, drawer contacts.

### Temperature Sensor
Reports temperature in **Celsius**. HomeKit displays in the user's preferred unit. Ensure the state value is a plain number (`22.1`, not `"22°C"`).

### Humidity Sensor
Reports relative humidity (0–100%).

### Luminance / Light Sensor
Reports lux. HKLS includes a check for abnormally high lux values (>100,000).

### Smoke Sensor
Binary smoke detected / not detected.

### Carbon Monoxide Sensor
Binary CO detected / not detected.

### Leak Sensor
Binary leak detected / not detected.

### Battery Service
All sensor types automatically expose a battery level characteristic. Configure the **Low Battery Alert** threshold in Plugin Config.

---

## Blinds & Windows

### Blind / Window Covering

Supports both on/off devices (open/closed) and dimmer devices (position 0–100%).

**Inversion options** (configurable per device):
- **Reverse open/close logic** — treat On as Closed, or On as Open
- **Reverse position** — treat 20% as 80% open (or vice versa)

### Window

Same as Blind but displayed as a Window in HomeKit.

---

## Thermostat

Largely supported. Supports:
- Current temperature reporting
- Target temperature setting
- Heating / Cooling / Auto / Off modes
- Setpoint heat and cool managed independently when mode changes
- Temperature unit conversion (plugin converts non-Celsius devices for HomeKit)

> Some fine-tuning may still be needed for complex multi-zone setups.

---

## Locks

Standard HomeKit lock — reports locked/unlocked state and accepts lock/unlock commands.

---

## Garage Door

Supports Garage Door state and open/close commands. MultiIO Insteon garage door devices are supported.

---

## Valve / Irrigation / Shower Head

Valve-type accessories supporting on/off. Tested and working; there is a known occasional Home app display refresh delay (opening the device tile forces a state refresh).

---

## Outlet

Same as Switch but displayed with an outlet icon in HomeKit.

---

## Security System

Security systems are a special case — there is no direct Indigo equivalent. HKLS implements a flexible mapping layer.

**Currently supported alarm panels:**
- **Paradox / Magellan / SP7000**
- **DSC Keypad**
- **VSS** (basic security system device)
- **AD2USB** (beta support)

HomeKit security states: Disarmed, Armed Stay, Armed Away, Armed Night, Triggered.

> Testing security systems is difficult without the actual hardware. If you have a supported system and encounter issues, please report on the forum with the [Troubleshoot menu output](Plugin-Menu-Items#troubleshoot-items).

---

## Cameras

Camera support is a major feature. See the dedicated [Camera Setup](Camera-Setup) page for full configuration details.

**Supported camera integrations:**
- **Blue Iris** (via the Blue Iris Indigo plugin) — full support including motion detection, doorbell, Opus audio, stream intelligence
- **SecuritySpy** (via FlyingDiver's SecuritySpy plugin) — live stream, doorbell, Opus audio, motion events

**Camera features:**
- Live RTSP → HomeKit stream transcoding / passthrough
- Opus audio proxy (RTP/SRTP clock-rate translation for HomeKit compatibility)
- Doorbell integration — any on/off Indigo device can trigger a HomeKit doorbell notification with live camera feed
- Motion sensor — BI cameras register as HomeKit motion sensors; act on motion events in the Home app

---

## Action Groups

All Indigo action groups are automatically available as **Switch** type accessories. Use the Home app icon picker to display them as Switch, Fan, or Outlet as appropriate.

---

## Device Compatibility Notes

| HKLS Behaviour | Why |
|---|---|
| Greyed devices in config list | Already published to another bridge — edit that bridge to manage them |
| Wrong state type → shows 0 | Temperature/humidity state must be a plain number |
| Bridge fails after Show All | Incompatible type selected — unpublish all devices, check logs, re-add carefully |
| Duplicate device needed | Use Masquerade plugin or Indigo Virtual Device |

---

→ [Camera Setup](Camera-Setup) — configure BlueIris and SecuritySpy cameras
