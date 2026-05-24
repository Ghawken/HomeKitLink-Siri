![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Quick Start

Get your first Indigo device into Apple HomeKit in five minutes.

---

## Step 1 — Create a HomeKitLink Bridge Device

1. In Indigo, go to **Devices → New Device…**
2. Select **Plugin → HomeKitLink Siri**
3. Choose device type: **HomeKitLink Bridge**
4. Name it something descriptive, e.g. *HomeKitLink Bridge — Lights*
5. The bridge device config dialog will open

---

## Step 2 — Publish an Indigo Device

Inside the bridge config dialog:

![Device Config 1](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/DeviceConfig1.png?raw=true)

1. **Select a device** from the dropdown list  
   - Use the category filters (Sensors, Lights, etc.) to narrow the list
2. **Check the "Publish Device" checkbox**
3. **Name the device** — this is the HomeKit name Siri will use  
   *(HomeKit automatically removes the Room prefix in the Home app)*
4. **Select the HomeKit device type**  
   - For a light, pick **Lightbulb** — HKLS auto-detects whether it's a colour, dimmer, or switch
5. Click **Save Device**

You'll see a log message confirming the device has been published.

Repeat for as many devices as you like (up to 95 per bridge), then click **Save** in the dialog to restart the bridge.

---

## Step 3 — Pair with the Home App

Once the bridge is running:

1. In the bridge config dialog, click **Show QR Code**
2. A web page opens with a pairing QR code
3. On your iPhone/iPad, open the **Home** app
4. Tap **+** (top right) → **Add Accessory**
5. Scan the QR code
6. Follow the Home app prompts to name the bridge and assign rooms
7. Your devices will appear — assign them to rooms as desired

![HomeKit Pairing](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/HomeKit.png?raw=true)

---

## Step 4 — Control via Siri

With the bridge paired, all published devices are available to Siri immediately:

- *"Hey Siri, turn on the Kitchen Light"*
- *"Hey Siri, set the Living Room to 50%"*
- *"Hey Siri, what's the temperature in the Office?"*
- *"Hey Siri, close the bedroom blinds"*

---

## Adding More Devices Later

1. Open the HomeKitLink Bridge device in Indigo (Edit Device)
2. Select a new device, check Publish, configure, click Save Device
3. New devices appear in the Home app's default room automatically
4. Click **Save** in the dialog when done — the bridge restarts briefly

---

## Key Concepts

| Concept | Detail |
|---|---|
| **One bridge per device** | A device can only be published to one HKLS bridge at a time |
| **95 device limit** | Each bridge supports up to 95 Indigo devices |
| **Unlimited bridges** | Create as many HKLS bridge devices as needed |
| **Type changes need a restart** | Changing a device's HomeKit type? Remove it first, Save, then re-add |
| **Settings persist** | All configuration is stored in the Indigo database |

---

## Troubleshooting Quick Start

**Bridge not visible in Home app?**
→ Run **Plugins → HomeKitLink Siri → ℹ️ Troubleshoot 2 – Network Trouble Shooting**  
See [Troubleshooting](Troubleshooting) for the full guide.

→ [Setup & Configuration](Setup-and-Configuration) for detailed options
