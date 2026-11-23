![HomeKitLink Siri Banner](https://github.com/Ghawken/HomeKitLink-Siri/blob/add_controls/Images/banner.png?raw=true)

# Changelog

Complete version history for HomeKitLink Siri.

---

## 0.8.62 — 2026-11-23

### 🔧 Change
- **Startup log**: the session banner shows the plugin, Indigo, the Mac (macOS version and name, model, name), its CPU, cores and memory, Python, HAP-python and zeroconf versions, FFmpeg (version, and its path over several lines), how many bridges and published devices, HKSV Recorders, the main settings (improved live view, BlueIris remote stream, log level), the Mac's IP addresses and the network settings. The version is in the session's header line (🆕 after an update, with the version it was upgraded from). Each camera's talk, control, UniFi capabilities and HKSV setup lines, and the live view line, are now debug only; warnings are unchanged

---

## 0.8.61 — 2026-11-23

### 🔧 Change
- **HKSV records a BlueIris camera's sub-stream when it suits**: the stream check also tries BlueIris streams 0–2 with `&decode=-1` (the camera's sub-stream). Of streams equally close to the size the hub asked for, a sub-stream is preferred, also when re-encoding. With the camera's sub-stream at 1080p H.264 and a BlueIris stream set to Direct-to-wire, nothing re-encodes for HKSV: neither BlueIris nor HKLS. The check takes longer (six streams per BlueIris camera) → [Camera Setup](Camera-Setup#best-record-the-cameras-own-sub-stream-blueiris-no-re-encoding-at-all)

---

## 0.8.60 — 2026-11-23

### 🔧 Change
- **Show Device Publications is grouped by bridge**: each bridge has a line with its name, state (running, disabled, not running or missing), port, configuration number, pairing and accessory count. Each device shows its accessory ID and generation (Gen), whether it's in HomeKit now, and its sensor, linked doorbell (by name) and HKSV Recorder. It ends with totals → [Plugin Menu Items](Plugin-Menu-Items#show-device-publications)
- **Identify Devices Running / Not Running** (also at the end of Troubleshoot 1) uses the same columns, sorted by bridge, with a count for each section. A device deleted from Indigo is listed without an error in the log. A new section lists devices published to a bridge that's disabled, deleted or not set
- **Orphaned devices** (their bridge was deleted): Show Device Publications reads published devices from Indigo as it runs, so they're always listed, under MISSING, with what to do next
- **Move Accessories to another Bridge**: a **Confirm** tick is needed. Pressed without it, it lists the devices that would move and changes nothing. From Bridge shows each bridge's name (or DELETED) and how many are published to it. Each moved device is logged with its new accessory ID, then the total. A moved device whose new ID another device on the bridge has gets the next free generation. To Bridge lists only bridges. The source bridge restarts too when it still exists; a disabled destination isn't enabled. A moved camera's saved HKSV Home app settings are cleared (it's a new accessory to Home). Choosing the same bridge twice does nothing. Settings left by a pre-release version are no longer read, so they can't publish forgotten devices → [Plugin Menu Items](Plugin-Menu-Items#move-accessories-to-another-bridge)
- **Unlink any Orphaned Devices**: also unpublishes devices with no bridge set, logs each one clearly, and no longer logs an error for a deleted device
- **Make Home Re-read a Bridge's Accessories** and **Reset Accessory / Bridge**: the Bridge list shows only bridges

---

## 0.8.59 — 2026-11-22

### 🔧 Change
- **A device unpublished and published again is a new accessory to Home**: unpublishing raises its HomeKit identity generation, so it comes back with a new accessory ID. With the same ID, Home (or a home hub with an old copy) matched it to its old record and brought back what it kept, e.g. a camera's old control showing No Response, and recordings not saved. A device published for the first time keeps its usual ID; moving a device to another bridge is unchanged. Published again, a camera's saved HKSV Home app settings start again too, as Home's do → [Plugin Menu Items](Plugin-Menu-Items#new-homekit-identity-for-a-device-emergency)

---

## 0.8.58 — 2026-11-22

### ✨ New
- **New HomeKit Identity for a Device (emergency)** menu item: gives a published device a new accessory ID, so Home removes the old accessory, with anything Home kept for it, and adds the device as new. For when Home keeps something that's no longer published (e.g. a camera's old control showing No Response), and neither unpublishing and publishing again (Home reuses its old record, as the ID is the same) nor Make Home Re-read a Bridge's Accessories clears it. Its room, name, automations, notifications and a camera's Recording Options are set again in Home; its HomeKitLink settings and HKSV Recorder are kept. Only its bridge restarts → [Plugin Menu Items](Plugin-Menu-Items#new-homekit-identity-for-a-device-emergency)

### 🔧 Change
- **Unpublishing keeps a device's identity generation**, so publishing it again doesn't bring back the accessory ID a New HomeKit Identity replaced

---

## 0.8.57 — 2026-11-22

### ✨ New
- **Make Home Re-read a Bridge's Accessories** menu item: raises a bridge's configuration number, so every home hub, iPhone and iPad fetches its accessories again and drops any no longer published (e.g. an extra camera accessory showing No Response, which a hub kept putting back). The bridge stays paired and running, and nothing is unpublished → [Plugin Menu Items](Plugin-Menu-Items#make-home-re-read-a-bridges-accessories)

---

## 0.8.56 — 2026-11-22

### 🔧 Change
- **Garage Door: `doorState` as words too**: open, closed, opening, closing, stopped or reversing, in any case, as well as 0-5. A `doorState` it can't read now falls back to the on/off state (it left the tile unchanged), and the log warns once with the value → [Supported Devices](Supported-Devices#garage-door)

---

## 0.8.55 — 2026-11-22

### ✨ New
- **Garage Door: Enable to Invert Controls**, for devices that turn **on to open**, e.g. a gate (Nice IT4WIFI): Home's Open turns the device on and Close turns it off, and an on/off state reads on as open. Each open or close from Home is logged → [Supported Devices](Supported-Devices#garage-door)
- **Garage Door: obstruction from an `obstructed` state**, when the device has one: it sets and clears Home's obstruction warning

### 🐛 Fix
- **Garage Door: Stopped shows as Stopped** in Home (it showed as Open); the target stays where it was
- **Cameras: a restarted bridge no longer checks all its camera streams again**: each bridge start added its cameras again, unchecked, so every camera was checked again one by one, and a camera published again re-encoded its live view until its turn (15 minutes on a bridge of cameras). A camera keeps its stream check while its stream is the same

### 🔧 Change
- **Unpublishing a camera an HKSV Recorder records** now warns that Home deletes its recordings and turns its recording off, that its Recorder and settings are kept, to Save without unpublishing to change settings, and to restart the phone if the Home app then shows an old tile or no Recording Options

---

## 0.8.54 — 2026-11-22

### ✨ New
- **Doorbell notifications show who rang**: Home asks for a snapshot for the ring notification straight away, and HKLS used to answer with the last saved image, which could be minutes old (often an empty doorstep). A ring now fetches a new snapshot at once, past the snapshot refresh limit, and the notification's snapshot waits for it (up to 2 seconds, then the last image). Blue Iris, SecuritySpy and UniFi cameras, for every kind of ring: the camera's own doorbell, DoorBell Linked and the doorbell action → [Camera Setup](Camera-Setup#doorbell-integration)

---

## 0.8.53 — 2026-11-22

### ✨ New
- **A camera can ring from a UniFi doorbell's button**: choose the doorbell (e.g. the G6 Entry) in a camera's **DoorBell Linked**, and pressing its button rings that camera in Home as well as the doorbell itself. E.g. a Blue Iris gate camera beside a G6 Entry. Works for Blue Iris, SecuritySpy and UniFi cameras; the log shows `[Gate] doorbell ring from 'G6 Entry' sent to HomeKit` → [Camera Setup](Camera-Setup#doorbell-integration)

### 🔧 Change
- **DoorBell Linked list**: *No DoorBell* first, then **Camera doorbells** (with their model), then **On/off devices**, each sorted by name; the camera being set up isn't listed

### 🐛 Fix
- The UniFi **G6 Pro Entry** (model "UVC G6 Pro Entry") is recognised as a doorbell without ticking *Treat as a doorbell*

---

## 0.8.52 — 2026-11-22

### 🔧 Change
- **Bridge dialog, Save Device on an already published device now logs**: what changed (e.g. *audioSelector, doorbellId changed*), or *no changes*, and that the bridge restarts when you close the dialog with Save. Before, only publishing or unpublishing logged anything, so it was easy to miss pressing Save Device

---

## 0.8.51 — 2026-11-22

### 🐛 Fix
- **Unpublishing a camera an HKSV Recorder still records keeps its settings** (audio, motion, doorbell, talk, control): the Recorder keeps it in HomeKit, so they're there when it's published again. Other devices still have their settings removed on unpublish
- **Bridge dialog, DoorBell Linked**: a camera with no doorbell chosen showed an empty menu; it now shows *No DoorBell Device Selected*
- **"Looking for Bridge … but reached Bridge …" warnings right after a restart**: while bridges restart, Home hubs also try ports they remember from long ago, then find each bridge on its own port. These attempts in the first 2 minutes after a bridge starts or stops are now only counted (Troubleshoot 4), not warned; a hub still reaching the wrong bridge after that is warned as before

---

## 0.8.50 — 2026-11-22

### ✨ New
- **Talk through a HomePod, Apple TV or Sonos**: a camera's Home app talk can be streamed live to a speaker, for as long as you talk, and stops when you stop. Choose it in **Talk through**. → [Camera Setup](Camera-Setup#two-way-audio-v0817)
  - **HomePod / Apple TV** (Apple TV plugin): over AirPlay, using the Apple TV plugin's existing Send Command action, so nothing to change there. Plays a little late (about 2 s).
  - **Sonos** (Sonos plugin players): played as a Sonos audio clip, the speaker's own announcement feature: the music is lowered, then carries on afterwards. Needs a Sonos S2 speaker that supports audio clips. Very little delay
  - The speaker fetches the stream from the Mac on **Plugin Config → Talk stream port** (default 8891). A speaker on another subnet / VLAN needs that port allowed; the log warns if a speaker never fetches the stream, and reports a Sonos that can't play it

### 🔧 Change
- *Two-way audio: mute the camera while you talk* is now **off by default**: you hear the visitor all the time, so you don't miss their reply, at the cost of maybe hearing yourself if the speaker is near the camera's microphone. A setting you've already saved keeps its value

---

## 0.8.49 — 2026-11-22

### ✨ New
- **Talk through another camera** (all camera types): the Home app's talk button can speak through a UniFi Protect camera's speaker, e.g. a Blue Iris gate camera talking through a G6 Entry. Choose it in **Talk through** in the camera's settings (needs Support Audio on). Blue Iris cameras already show the talk button; until now their talk went nowhere. → [Camera Setup](Camera-Setup#two-way-audio-v0817)
- *Two-way audio: mute the camera while you talk* now applies to any talk, including Talk through

---

## 0.8.48 — 2026-11-22

### ✨ New
- **HKSV:** unpublishing a camera that an HKSV Recorder still records now logs a warning naming the Recorder (delete it, or point it at another camera, to remove the camera); a Recorder whose camera isn't published logs why nothing is recorded
- **Camera control device** (all camera types): a gate, door or light that's part of the camera's own accessory, e.g. a doorbell camera with its gate. The Home app shows it in the camera's nearby accessories and room, like any accessory (not on the video), so it's the same as publishing the device separately, set up with the camera. Its options show once a device is chosen. Any on/off device or action group, shown as a **Lock** (Home asks for Face ID) or a **Switch**; **momentary** (shows open for a few seconds) or **follows the device**. Lock uses Indigo's lock convention (unlock = off), so a UniFi Access door works directly. Off by default. → [Camera Setup](Camera-Setup#control-device-v0848)

---

## 0.8.47 — 2026-11-17

### ✨ New
- **Heat only** option for thermostats published as Thermostat (e.g. floor heating such as Heatit TF021, or virtual heating thermostats): the Home app offers only Off and Heat with no Auto range, so asking Siri to change the temperature just changes the target instead of switching to Auto with a range. Siri's Auto request is treated as Heat, as Home Assistant does. Ticked already in bridge settings for thermostats without a cool setpoint; devices already published don't change until it's ticked

---

## 0.8.46 — 2026-11-16

### 🔧 Fix
- Heater-Cooler zones (e.g. Actron Que): turning a zone on in the Home app while the main unit is off no longer leaves the zone tile showing on. The zone isn't changed, the log says to turn the main unit on first, and the tile goes back to off (the same as Actron's own Set Zone action). It never started the main unit

---

## 0.8.45 — 2026-11-15

### 🔧 Fix
- Blue Iris remote viewing check: when Blue Iris returns nothing (e.g. busy serving many streams), the log now says it couldn't read the stream to check it, instead of wrongly suggesting the Direct-to-wire setting. Remote views use Stream 2 until the next check

---

## 0.8.44 — 2026-11-15

### 📷 Improved live view (on by default)
New setting **Plugin Config → Live view: Improved live view**, on by default; untick it for the previous behaviour, exactly. It does what Home Assistant, homebridge-unifi-protect, Scrypted and homebridge-camera-ffmpeg do, mainly for **Apple TV** and **remote viewing** that a home hub relays:
- **Matching video ports:** video is sent from the port HomeKit is told we send from, so the viewer's reports come back. Until now it was sent from a random port; every other project keeps these the same
- **1200-byte packets**, which fit relayed and IPv6 paths
- **Re-encoded video is sized and tuned for the request:** scaled down to the size HomeKit asked for (never up, keeping the shape), one slice per frame, a keyframe every 4 s instead of 0.5 s, a 2x buffer, and HomeKit's level and frame rate
- **Remote views start at 720p:** HomeKit starts a remote view small (e.g. 640x360 @ 132k) and nearly always asks for 1280x720 @ 299k a few seconds later, a change HKLS can't follow on a running stream, so remote views stayed low quality. A 640-1279 wide request now starts at 1280x720 and at least 299k; Blue Iris and UniFi still use their remote stream. Apple Watch-size requests are unchanged
- **Copied streams keep the camera's picture**: e.g. Blue Iris passthrough only gets the ports and packet size
- Each stream logs what was applied. See [Camera Setup → Improved Live View](Camera-Setup#improved-live-view-v0844)

### 📷 Camera fixes
- **Cameras on more than one bridge are all checked.** The background stream check ran once, after the first bridge started, so cameras on bridges that started later (or were restarted) were never checked: no stream data and no remote stream, so a 5G view copied the full stream and never played. Unchecked cameras are now checked once startup has finished and whenever a bridge starts
- **No stream data yet: re-encode.** A camera not checked yet is re-encoded instead of copied, since copying passes on whatever the camera sends, which may not suit what HomeKit asked for. Once checked, its usual setting (e.g. copy) applies

---

## 0.8.43 — 2026-11-15

### 🔌 Saved bridge ports: safer
- **A moved bridge shows in Troubleshoot 4.** If a bridge's usual port isn't free at start, it moves, and 🔌 Bridge Ports now shows *"moved from 51846 at start"* with what to do (restart your home hub) until the plugin restarts. Before, the report showed it as saved ✅
- **`bridge_ports.json` is never lost or overwritten by mistake:** it's written to a temporary file and swapped in, so a crash mid-write can't leave half a file; and a file that can't be read (e.g. a bad hand edit, or a port above 65535) is left as it is, with a warning, instead of being replaced with just one bridge
- **Troubleshoot 4's fix for a bad, missing or duplicated file** is now the exact line to put in the file, built from the ports the bridges are running on now (which Home devices already know), instead of "delete the file", which would have given bridges new ports
- The wrong-bridge warning is limited to once every 10 minutes per device however many bridges it names, and Troubleshoot 4 keeps at most 50 entries per bridge
- Troubleshoot 4 is easier to read: problems are logged as warnings (no code location in front), wrong-bridge attempts for bridges that aren't here are one line per device, and the list shows the 10 most recent

### 🔁 Moving from Durosity's development build (unifi-hksv-twoway)
- **UniFi cameras keep working:** that build's camera type `UniFiCamera` is changed to ours (UniFi Protect Camera) at startup, and the camera stays the same accessory in Home
- **"New HomeKit identity" devices keep their accessory ID**, so Home doesn't add them again
- **HKSV:** that build switched HKSV on with a camera setting; here a camera needs a **HomeKit Secure Video Recorder** device. The log says so once for each camera that had it on and has no Recorder yet
- **Two-way audio:** that build switched it on by itself for doorbells and cameras with a speaker; here it's the camera's *Two-way audio* setting. The log says so once for each of that build's UniFi cameras where it's off
- New hidden action **hklinkProtocolVersion** for Durosity's Virtual Doors plugin. It answers 0 (this build doesn't support Virtual Doors & Windows states yet), so the plugin gets an answer instead of an error

---

## 0.8.42 — 2026-11-15

### 🔌 Troubleshoot 4 checks the saved bridge ports
- The **🔌 Bridge Ports** section now checks `bridge_ports.json` itself: that it's there and readable, that no two bridges are saved with the same port, and that every running bridge is on its saved port, with a ✅ line when all is well. Saved ports kept for deleted bridges are listed (harmless: those ports just aren't reused)

---

## 0.8.41 — 2026-11-15

### ⚠️ Warning when a Home device reaches the wrong bridge
- A Home device (home hub, iPhone, iPad) that remembers an **old port** for a bridge can reach a different bridge on it, and then shows the bridge it wanted as **No Response**. The bridge it reached sees nothing wrong, so until now nothing was logged. HomeKitLink now spots it, because each request names the bridge it's for, and logs a warning naming the device, the bridge it wanted and the bridge it reached, with what to do: restart that device so it looks the bridges up again. Repeats at most every 10 minutes per device and bridge
- **Troubleshoot 4** has a new **🔌 Bridge Ports** section: each bridge's port and whether it's the saved one, and every Home device that reached the wrong bridge since the plugin started (device, bridge it wanted, bridge it reached, how often, when). The problem is also listed under the bridge the device wanted, as an error while it's still happening and a warning once it has stopped

---

## 0.8.40 — 2026-11-15

### 🔌 Bridges keep their port (fixes "No Response" after adding a bridge)
- **Each bridge now keeps the same port** every time it starts. Ports used to be handed out in start order, so adding a bridge, or a change in the order bridges start, moved other bridges to the next port. Home apps and hubs remember each bridge's port, so they reached the wrong bridge, couldn't verify, and showed that bridge's accessories as **No Response** (even though they still worked from Indigo) until they looked the bridge up again
- Ports are saved in `bridge_ports.json` in the plugin's preferences folder. The first start after updating saves the ports bridges have now. A new bridge gets a port no other bridge has used
- If a bridge's usual port is taken by something else, it moves to a free one and the log warns that Home apps may show it as No Response for a while

---

## 0.8.39 — 2026-11-15

### 🧾 Quieter camera logging
- **Repeated short live views** (e.g. a Home widget that refreshes a camera's picture by opening a stream for a second or two, all day) are logged once: when the same device asks for the same size again within 10 minutes and its last view lasted under 5 seconds, that stream's lines go to debug level, with one line saying so. Normal logging resumes once the device has been quiet for 10 minutes. Real viewing (5 seconds or more) is always logged
- With **Debug HomeKit Camera** on, each snapshot is one debug line instead of eight

---

## 0.8.38 — 2026-11-15

### 📷 Blue Iris: faster live view start
- Blue Iris live views start about 1.7 s sooner: the quick-start options for reading the camera stream (`-probesize`/`-analyzeduration`) were placed where ffmpeg ignored them. Measured from request to first video: remote/small views 2.1 s → 0.4 s, local view 1.8 s → 1.2 s
- Helps viewers that only stay for the first frame, such as Home widgets refreshing a camera, which repeatedly start and stop a short stream

---

## 0.8.37 — 2026-11-15

### 🌡️ HomeKitLink Sensor
- New device type **HomeKitLink Sensor**: publishes one state of another Indigo device as a HomeKit sensor of its own (Temperature, Humidity, Light, Contact, Motion, Occupancy, Leak, Smoke, CO or CO2), with its own name, room and bridge. Make one per reading, e.g. a weather gateway's outdoor temperature, humidity and rain, each as its own tile. Nothing is changed on the device it mirrors
- It's an ordinary Indigo sensor that follows its source state, so it can also be used in Indigo triggers and Control Pages
- On/off sensors are "detected" when the state is true, false, or equals a value you give (e.g. `rain`)
- Publish it from its own settings (**Publish to bridge** and **HomeKit name**) or from a bridge (**Select Type to List → HomeKitLink Buttons and Sensors**)
- HomeKitLink Sensors and HomeKit Buttons have a **HomeKit name** in their own settings, used when publishing from there. Before, they were published under the Indigo name at that moment, which for a new device is still "new device N". Left empty, a name is suggested for you to check

### 🔘 HomeKit Buttons
- If the bridge a HomeKit Buttons (or Sensor) device is published to is deleted, its **Publish to bridge** menu now keeps showing it as deleted instead of switching to "Not published", so saving its settings doesn't unpublish it by accident

### 🧾 Logging
- Deleting a published device now logs a plain warning ("… was deleted while published to HomeKit: its bridge restarts …") instead of an error with code line numbers; the internal "Deleting item" details are debug only

---

## 0.8.36 — 2026-11-15

### 🧹 Fewer settings stored on your devices
- **Unpublishing** a device now removes all of HomeKitLink's settings from it, instead of leaving them behind as empty values
- **Saving** a published device keeps only the settings its HomeKit type uses (e.g. a Switch no longer stores temperature, camera or vacuum settings; changing a Vacuum to a Switch drops its vacuum settings). Older devices are tidied the next time they're saved

---

## 0.8.35 — 2026-11-15

### 🛠️ Device updates
- On/off sensors (Contact, Motion, Occupancy, Leak, Smoke, CO, CO2) published with a state of their own (e.g. a chosen `motion` state, or an analog `sensorValue`) now follow only that state: a change of the device's on/off state no longer overwrites them, and they're no longer written twice. Relays and on/off devices published as sensors still follow their on/off state, as before
- Blue Iris and SecuritySpy cameras no longer try to apply an on/off change (a camera has no on/off tile), which could log a "Nonetype error" line

---

## 0.8.34 — 2026-11-15

### 📋 Bridge settings: finding devices
- New **Search** box above the device list: type part of a name (or several words, in any order) and press **Find**, and the list shows only matching devices; **Clear** shows them all again. Works with every list type. Pressing Return in the box applies the search and keeps the window open, rather than closing it
- The device menu is now labelled **Device to Publish**
- Device lists are now sorted properly: ignoring capitals (so `appleTV…` no longer comes after `Zone…`) and with numbers in order (`Zone 2` before `Zone 10`)
- New list types: **Indigo Thermostats**, **Indigo Fans (Speed Control)**, **Indigo Sprinklers**, **Plugin Devices** (every third-party plugin's devices, with a sub-header per plugin) and **Cameras (all)** (Blue Iris, SecuritySpy and UniFi Protect together, each under its own sub-header)
- Devices on other bridges show the bridge's name instead of its number, and are sorted by device name
- HomeKitLink's own bridges and HKSV Recorders are no longer listed (they can't be published); an empty list says so
- Opening a bridge's settings no longer shows the last device's options (greyed out): device options appear only once a device is chosen, and are cleared again when the list type changes or a search is run

---

## 0.8.33 — 2026-11-15

### 🔔 Linked doorbells
- A device used as a camera's **DoorBell Linked** that is also published itself (e.g. as a switch or sensor) now updates both: the camera rings **and** its own tile changes. Before, only one of them worked, and the device's own tile could be attached to the camera instead
- One doorbell linked to **several cameras** now rings all of them (before, only the first)
- Restarting a bridge no longer leaves old linked-doorbell entries behind, and a doorbell that's also published keeps its own tile after a bridge restart
- Each device's update is handled on its own, so a problem updating one entry no longer stops the others

---

## 0.8.32 — 2026-11-15

### 🌫️ Air quality sensors
- The automatic state choice no longer picks a sensor's battery (e.g. Ecowitt's `pm25Batt1`) and prefers the live reading over a 24-hour average (`pm25Ch1` before `pm25Ch1Avg24h`)

---

## 0.8.31 — 2026-11-15

### ❄️ Heater-Cooler
- Clearer **Zone of** setting: "Not a zone - a main unit or a single AC" for a main unit, and a heading over the main units a zone can belong to. The help says each zone is published separately

---

## 0.8.30 — 2026-11-15

### ❄️ Heater-Cooler
- Actron Que devices (main unit and zones) now default to **HeaterCooler** when publishing; zones get **Zone of** filled in. Other thermostats still default to Thermostat. Devices already published keep their type

---

## 0.8.29 — 2026-11-15

### ❄️ Heater-Cooler (air conditioners)
- New HomeKit type **Heater-Cooler** for any Indigo thermostat, offered alongside Thermostat (existing thermostats are unchanged). The Home app shows its air conditioner tile: a power button separate from the mode, Heat / Cool / Auto, and heat and cool targets
- **Zones** of ducted systems: set **Zone of** to the main unit (filled in automatically for Actron Que zones). A zone's power button only opens or closes that zone; it shows the main unit's mode and never changes the main unit's mode or power. Each zone uses its own targets, kept within the zone's current minimum and maximum (Actron's move with the main unit's setpoint), and the log says when a target is adjusted
- Only the modes and targets the thermostat supports are offered (a cooling-only AC gets Cool only); a thermostat whose plugin can't change modes keeps its power and mode as Indigo reports them
- Turning a main unit back on resumes its last mode. Fahrenheit thermostats are converted as for Thermostat
- Heating, cooling or idle comes from the thermostat's "heater on" and "cooler on" states; devices that don't set them show idle while running

---

## 0.8.28 — 2026-11-15

### 🌫️ Air quality sensors
- New HomeKit type **Air Quality Sensor**: the Home app's air quality tile, with any of PM2.5, PM10, VOC, NO2, ozone, CO2 and an air quality index (US AQI), each read from a state of the Indigo device
- The overall rating (Excellent, Good, Fair, Inferior, Poor) is the worst of the readings, using the same bands as Home Assistant: US EPA AQI bands for PM, ozone and the index; WHO guidance for VOC and NO2. CO2 is shown but not rated
- VOC, NO2 and ozone can be given in µg/m³ or ppb (converted for HomeKit)
- Devices with states named like `pm25`, `pm10`, `voc`, `no2` or `aqi` are offered it automatically, with those states pre-selected; it's also offered for temperature and humidity sensors. Battery level is shown when the device has one

---

## 0.8.27 — 2026-11-15

### 🤖 Robot vacuums and lawn mowers
- New HomeKit types **Vacuum** and **LawnMower** for any device. HomeKit has no vacuum or mower tile outside Matter, so, as in Home Assistant, they show as a switch: on starts, off sends it home. "Hey Siri, turn on the vacuum" works
- Uses the device's on/off, or choose **Start** and **Stop / go home** action groups and the state that shows it's running (e.g. `status` is one of `cleaning, spotCleaning`)

### 🔘 HomeKit Buttons: Indigo starts Home app automations
- New device type **HomeKit Buttons** (1–10 named buttons), published from its own settings (**Publish to bridge**) or from a bridge (**Select Type to List → HomeKitLink Buttons**). It does nothing in Indigo: it appears in the Home app as a button accessory, and the Home app decides what each single, double and long press does
- New action **Press a HomeKit Button** presses one from any Indigo trigger, schedule, action group or Control Page. This reaches what only the Home app controls: Matter or Apple-only devices, HomePod music, Home scenes
- A physical remote (e.g. a WallMote) is brought into Home the same way: give a Buttons device matching buttons and add the action to the remote's Indigo triggers
- States: last button, last press and when

### 🎥 HomeKit Secure Video
- A disabled Recorder no longer checks the camera's streams at every bridge start, and logs one line saying it's disabled. The Home app's routine re-writes after a restart are only logged when something actually changed

### 🛠️ Fixes
- Reopening an already-published device in a bridge's settings now shows its saved HomeKit type (and that type's settings), not the type HomeKitLink would detect

---

## 0.8.26 — 2026-11-14

### 📷 Cameras
- UniFi **G6 Entry** is now a HomeKit doorbell automatically (its model name doesn't say "doorbell")
- Wiki: Blue Iris 6 notes from its change log — 6.0.9.16 or later for remote viewing, keep HomeKit streams H.264, keyframe rate, and web server IP bans

---

## 0.8.25 — 2026-11-14

### 📷 From PR #42 (thanks Durosity)
- **UniFi package camera**: a G4 Doorbell Pro / G6 Entry's package lens (the UniFi plugin's *Protect Package Camera* device) can be published as its own HomeKit camera. Motion includes package detection; its snapshot is grabbed from its own stream in the background
- **UniFi "Treat as a doorbell"** for models whose name doesn't say doorbell
- **UniFi portrait cameras** are offered portrait sizes (from the stream size the startup check saw), so HomeKit doesn't ask for landscape video they never send
- **HomeKit Secure Video**: a doorbell press keeps a recording going for 30 s (Recorder setting, on by default)
- **Two-way audio**: muting the camera while you talk can now be turned off in the plugin Config
- Not taken from the PR, for reasons in the PR review: the RTSP port 7447 rewrite, manual quality/size menus, renaming camera motion sensors, per-device new identities, hardware encoding for live view (measured: for the small remote-viewing re-encode it saves no CPU, as decoding the camera's stream is most of the cost) and a custom ffmpeg path. Virtual Doors & Windows waits for its companion plugin

---

## 0.8.24 — 2026-11-14

### 🎥 HomeKit Secure Video
- A recording that starts soon after the camera stream (re)starts now waits up to 8 s for its first few seconds of video, so it begins with the pre-roll instead of none
- Checked with SecuritySpy and UniFi Protect cameras as well as BlueIris: each camera's own streams are checked (SecuritySpy full size and resized; UniFi High, Medium and Low) and the best one is copied or re-encoded
- Debug HKSV shows how much video was held when each recording started
- Wiki: HomeKit Secure Video now explains how recording works, what it costs per camera, the risks of many cameras, and how to add HKSV to a camera already in the Home app (it must be re-added). With thanks to Durosity, whose PR #42 made this possible

---

## 0.8.23 — 2026-11-14

### 🎥 HomeKit Secure Video — fixes from the first real recordings
- A recording's pre-roll is now just the newest few seconds HomeKit asks for (it could be 13 s), and the start of the live video can no longer be sent twice
- Stream check: the keyframe interval is measured over a longer stretch and retried, and copy is judged on the typical gap (4 s or less, none over 8 s). BlueIris streams whose frame rate varies are reported with their range, e.g. "keyframe every 3.3-6.8 s"

---

## 0.8.22 — 2026-11-14

### 🎥 HomeKit Secure Video — recording
- **Recording now works**: while the Home app allows recording, the Recorder keeps the last few seconds of the camera in memory and sends motion (and doorbell) clips to the home hub, starting a few seconds before the motion
- **Stream check**: at bridge start each of the camera's streams is checked and logged. A stream that suits HomeKit (H.264, up to 1920×1080, keyframe every 4 s or less) is **copied** with almost no CPU; otherwise the best one is re-encoded with VideoToolbox
- **Usage on the Recorder device**: ffmpeg CPU and memory, data rate, seconds buffered, recordings today and the last recording's length and size
- New Recorder settings: copy on/off, and VideoToolbox or libx264 for re-encoding
- Nothing runs while the Home app has recording off for the camera

---

## 0.8.21 — 2026-11-14

### 🎥 HomeKit Secure Video — preview
- The camera's recording services now match the PR #42 version that HomeKit accepted: the standard 16:9 recording sizes from 1920×1080 down to 320×180, and the same characteristics. 0.8.20's motion-sensor link and doorbell change are undone
- New **Debug HomeKit Secure Video** option in the plugin Config: shows what the home hub reads and writes for Recorder cameras, and their data stream, in the Indigo log

---

## 0.8.19 — 2026-11-14

### 🎥 HomeKit Secure Video — preview (phase 1)
- New device type **HomeKit Secure Video Recorder**: adds HKSV to one camera. Cameras without a Recorder are unchanged
- This version adds the camera's Recording Options to the Home app, remembers what the hub and Home app choose, and accepts the hub's encrypted data stream. **Clips aren't recorded yet**; that comes in a later version
- The Recorder's states show the Home app's switches, the recording format the hub chose and whether the hub is connected
- Based on the HKSV work in PR #42 (thanks Durosity), with the data stream limited to the hub that set it up

---

## 0.8.18 — 2026-11-14

### 🎙️ UniFi Protect two-way audio fixes
- The camera's sound no longer freezes when you start talking: the Protect talk session now opens in the background, even if the console is slow to answer
- When HomeKit uses longer audio packets (often away from home), the camera's sound is now muted cleanly while you talk, instead of glitching

---

## 0.8.17 — 2026-11-11

### 🎙️ UniFi Protect two-way audio
- Talk from the Home app through UniFi doorbells and cameras with a speaker (UniFi plugin by Durosity)
- Turn on **Two-way Audio (talk)** in the camera's HomeKitLink settings; Support Audio must be on
- The camera's own audio is muted while you talk, to stop your voice echoing back
- Based on the two-way audio in PR #42 (thanks Durosity)

---

## 0.8.16 — 2026-11-11

### 📷 Camera snapshots
- Fixed camera tiles showing the default images for several minutes after the plugin starts. The startup camera stream check now runs on its own, so snapshots are fetched straight away
- Shorter mDNS start-up debug line per bridge

---

## 0.8.15 — 2026-11-11

### 🏠 HomeKit library updates (part 2)
- **Fewer Home app reloads:** a bridge's accessory list is no longer treated as changed just because a device's value changed, so the Home app stops re-downloading every bridge after most plugin restarts. Expect one final reload after updating
- **Camera snapshots:** a request arriving while a snapshot was being fetched closed the connection and lost the snapshot; requests and updates now wait their turn
- Faster bridge start-up: device values are no longer read just to check for changes

---

## 0.8.14 — 2026-11-11

### 🔒 HomeKit library updates
Fixes and hardening brought in from the current HAP-python library:
- **Pairing:** an unpaired bridge can no longer be paired without the setup code by a specially crafted request; malformed pairing data is rejected; after 5 wrong setup codes, pairing pauses for 60 seconds
- **Cameras:** snapshots are only sent to paired Home devices; the stream address from the Home app is checked before it's used
- **Fixed:** camera or pairing data of certain lengths could be corrupted; a closed connection was treated as an error; oversized requests are refused
- **Faster:** less copying when sending and receiving HomeKit data

---

## 0.8.13 — 2026-11-11

### 📷 UniFi Protect logging
- Each UniFi camera logs its setup at start-up: plugin, model, streams found, doorbell, motion and audio
- Snapshot problems are logged once with the reason (e.g. HTTP 401 - check the controller's API key), and again when they recover
- Doorbell rings are logged
- Stream URLs are masked in all log lines

---

## 0.8.12 — 2026-11-11

### 📷 UniFi Protect cameras
- New camera type **UniFi Protect Camera**, for cameras from the Durosity UniFi plugin or kw123's uniFiAP plugin
- Live video, snapshots, Opus audio, motion and doorbell; away from home the Low stream is re-encoded to the size HomeKit asks for
- New camera auto-detect picks the right camera type (also fixes SecuritySpy cameras defaulting to Blue Iris)
- See [Camera Setup → UniFi Protect](Camera-Setup#unifi-protect-v0812)

---

## 0.8.11 — 2026-11-11

### 🛠️ Fixes (thanks to Durosity, PR #42)
- Garage doors: start-up target state is now always open or closed
- Cameras: a stream stopped by the Home app while still starting no longer leaves ffmpeg and the audio running
- No more errors when the Home app asks for an accessory that was just unpublished
- Unpublishing a device is more reliable
- Clearer log message when a camera stream has no video
- Removed unused code

---

## 0.8.10 — 2026-11-10

### 📷 Blue Iris remote / mobile camera viewing
- Away from home, cameras now use a Blue Iris stream re-encoded to the size and bitrate HomeKit asks for (e.g. 640×360 at 132 kbps), instead of the full-resolution Stream 2. At-home Wi-Fi viewing is unchanged
- New Plugin Config option **BlueIris Remote Viewing Stream** (Stream 0 default, Stream 1, Off)
- Each camera's remote stream is checked at startup; if Blue Iris doesn't resize it, a warning explains what to change
- See [Camera Setup → Remote / Mobile Viewing](Camera-Setup#remote--mobile-viewing--blue-iris-v0809)

### 🔊 Remote viewing audio
- Fixed no sound away from home: the longer audio packets HomeKit asks for remotely were too big and stopped the audio
- Audio RTCP sender reports are now sent to HomeKit (SRTCP)
- Negotiated audio settings are now included in the camera debug log

---

## 0.8.08 — 2026-11-10

### 🔐 New: Troubleshoot 4 — HomeKit Pairing & Security Keys
- New menu item that checks each bridge's pairing and security keys, Home users and connected Home hubs
- Clear ✅ / ⚠️ / ❌ result per bridge, a fix for each problem, and a guide to common HomeKit issues
- See [Plugin Menu Items](Plugin-Menu-Items) for details

### 📱 New: Show QR Code page
- QR code, setup code, pairing status and step-by-step instructions

### 🐛 Bug fixes
- Plugin could fail to load (stray `scipy` import)
- Battery levels now update in HomeKit
- Thermostat setpoints, security system startup state and Paradox arm/disarm
- Camera stream stability and clean-up
- Move Accessories, several crashes, Toggle Debug remembers its level
- Clearer log message when a Home app device can't connect to a bridge
- Removed the hidden legacy "unQuarantine files" option
- Typo and wording fixes

---

## 0.8.05 — 2026-04-07

### 🎵 Major: Camera Audio — Opus SRTP Proxy
- New **homekit_audio_proxy** library — a subprocess-based RTP/SRTP audio proxy solving the FFmpeg/HomeKit clock-rate mismatch for Opus audio
- FFmpeg uses 48 kHz timestamps (RFC 7587) but HomeKit expects the negotiated rate (e.g. 16 kHz). The proxy receives plain RTP from FFmpeg, converts timestamps, encrypts with SRTP (AES_CM_128_HMAC_SHA1_80), and forwards to the HomeKit client
- Blue Iris cameras default to **libopus** for audio
- SecuritySpy cameras gain the same libopus audio proxy support
- **⚠️ Breaking:** Existing cameras must be removed from Home and re-added for the Home app to reassess the audio stream. Results in significantly better audio quality

### 🎥 Major: Camera Stream Intelligence
- New `resolve_video_strategy()` function — uses `ffprobe` data to intelligently decide whether to copy or transcode each camera's video stream
- New Menu Item: **"Check or Update Camera Streams for Compatibility"** — runs ffprobe against all cameras and logs compatibility findings
- Auto-runs at startup in debug-only mode
- Automatic transcoding — when ffprobe detects incompatible streams (non-H.264, wrong pixel format, problematic GOP), HKLS auto-transcodes for HomeKit compatibility
- Updated `homekitlink_ffmpeg` library to include ffprobe binaries

### 🌐 Major: mDNS/Zeroconf Refactor
- Default IP version changed to **V4Only** (was All) — the HAP server is fundamentally IPv4-only; IPv6 mDNS served no purpose
- New `zeroconf_interfaces` parameter separates "which interfaces zeroconf listens on" from `interface_choice` (ip_version) — properly treated as mutually exclusive
- Fixed `advertised_address` conflation bug — was incorrectly passed as `interfaces` to AsyncZeroconf
- **mDNS Interfaces field unhidden** in Plugin Config — now visible under Advanced settings
- Auto-derive interfaces from server IP — when HAPServerIPAddress is set but mDNSInterfaces is empty, interface list auto-derived as `[HAPServerIPAddress]`

### 🔍 Major: Diagnostic & Troubleshooting Tools
- New Menu Item: **"ℹ️ Troubleshoot 2 — Network Trouble Shooting"** — comprehensive network diagnostic including LNA test, multicast, UDP, gateway, firewall, plugin config, port checks, DNS
- Definitive LNA test: uses `IP_MULTICAST_IF` bound to a non-loopback IP + sendto() to mDNS group — catches the exact failure mode when LNA is blocked
- New Menu Item: **"ℹ️ Troubleshoot 3 — Support mDNS Troubleshooting"** — mDNS/Bonjour diagnostic
- Enhanced **"Troubleshoot 1 — Support Information"** — now includes mDNS/network configuration details

### 🐍 Python 3.13 Compatibility
- Removed `async_timeout` dependency — replaced with Python 3.11+ built-in `asyncio.timeout`
- Updated libraries: `cryptography` 41→46, `orjson` 3.8→3.11, `h11` 0.14→0.16, `zeroconf` 0.131→0.148, `chacha20poly1305-reuseable` 0.12→0.13
- Removed `slugify` and `aiofiles` dependencies
- Added `cffi`, `pycparser`, `ifaddr` as explicit dependencies
- Fixed pip install success detection — glob matching for Python-version-prefixed filenames

### 🐛 Bug Fixes
- Removed dead `cryptography` import check — handled by preflight
- Fixed image snapshot timeout issue (from 0.7.02)
- Fixed interfaces not being selectable in plugin config (from 0.7.40)
- Fixed multi-NIC discovery — binding to all IPv4 interfaces fixes issues with 2+ active network connections

---

## 0.7.50

- Unhide mDNS zeroconf server address selection in Plugin Config (was previously hidden with `hidden="true"`)

---

## 0.7.45 – 0.7.46

- Fine tuning to support logging output
- mDNS refactor: IPv4 default for all users
- Plugin Menu: Support Logging Info improvements
- Bug fix: interfaces not being selectable in plugin config
- Bind to all IPv4 interfaces (fixes issues when 2 or more network connections are active)
- Logging changes and improvements

---

## 0.7.40

- Refactor mDNS — IPv4 default for all users
- Add Plugin Menu: Support Logging Info item
- Bug fix: interfaces not being selectable in plugin config
- Bind to all IPv4 interfaces (should fix issues when 2+ network connections active)
- Logging improvements

---

## 0.7.30

- **Major: Blue Iris camera stream intelligence** — checks streams and decides best passthrough vs. transcode approach
- New Menu Item: **"Check or Update Camera Streams"** — run after modifying Blue Iris web server settings
- Automatic transcoding when incompatible streams are detected
- Added image for optimal Blue Iris Profile 2 settings
- Updated `homekitlink_ffmpeg` library to include `ffprobe` binaries (published to PyPI)

---

## 0.7.15

- Add audio proxy and libopus support for **SecuritySpy** cameras

---

## 0.7.10

- **Major: Opus audio proxy** — solves FFmpeg/HomeKit clock-rate mismatch
- Blue Iris cameras default to libopus audio (requires camera re-add in Home app for existing setups — delivers much better audio quality)
- Fix for logging menu item compatibility with new Python changes

---

## 0.7.02

- Fix for image snapshot timeout failure
- Changed pip success detection to work with new Python version filename format

---

## 0.7.01

- Changed pip success library checking to manage new Python version
- Library updates and deletions
- Removed `async_timeout` dependency
- Updated all libraries to latest compatible versions

---

## 0.6.76

- Update zeroconf to version 0.146

---

## 0.6.75

- **Support for FlyingDiver's SecuritySpy plugin** — enables SecuritySpy camera types in HKLS
- Few bug fixes for deleting bridges without restarting
- Add support for **Motion Events** from SecuritySpy (was not an option previously)
- Add support for **Doorbell** and trigger on doorbell press (Home app shows pop-up video notification)

---

## 0.6.74

- Support for FlyingDiver's SecuritySpy plugin (initial commit, fine tuning)

---

## 0.6.73

- Add check for missing deviceID — prevents crashes when device references are stale

---

## 0.6.40

### Camera Handling Updates
- Refactor FFmpeg and camera handling — BlueIris working well
- Use TCP for `rtp_transport` — avoids errors and slight slowdown from FFmpeg UDP
- Speed up stream checks and closing unnecessary streams
- Attempt to fix OS 17.2 AppleTV issue where it opens all camera streams simultaneously

### New Camera Settings
- **Camera Max Refresh Time** — sets maximum refresh interval per camera; Home app requests are throttled to this rate
- **Passive Camera Update Image Time** — controls how often HKLS updates the stored image buffer when Home app is not actively viewing
- **Image Width** setting

---

## 0.6.0

### New HomeKit Architecture (iOS 16.4)
- After iOS 16.4, the Home app may close/reopen connections more aggressively without a Home Hub — this is normal; a Home Hub eliminates this behaviour
- Spins up HKLS's own Zeroconf async server shared by all bridges, minimising overhead
- Adds Advanced mDNS Options in Plugin Config
- Adds **Reset Accessory / Bridge** menu item
- Bump python-zeroconf to 0.56
- Bump h11 to latest dev version
- Adds debug10 logging for very verbose mDNS (file only)
- Attempt to fix Valve/Irrigation/ShowerHead devices — resolved
- Add HKLS support for AD2USB security systems (beta, thanks ab39870)

---

## 0.3.3

- Use `address` if `xaddress` is not available in SecuritySpy cameras

---

## 0.3.2

- Bug fixes for Thermostat device handling
- Fix leftover Fahrenheit → Celsius conversion issue
- Manage SetpointHeat/SetpointCool independently when mode changes
- Updated VSS security system state mapping

---

## 0.2.31

- Reject non-camera devices when trying to configure camera type
- **Security System support** — Paradox/Magellan/SP7000, VSS, DSC Keypad

---

## 0.2.29

- Add support for **Window** accessories

---

## 0.2.28

- **Battery Service** added to all sensor types
- **Low Battery Alert** threshold setting in Plugin Config
- **Window Blinds** support with position (0–100%) and inverse control options

---

## 0.2.24

- Dual binary FFmpeg supporting both M1 (Apple Silicon) and x86 Macs
- Support for MultiIO Garage Door (Insteon) devices
- Fix for empty pluginProps integer conversion

---

## 0.2.19

- **Locks** — lock/unlock control and state reporting
- **Garage Doors** — open/close control
- **Fan** (simple) and **Fan V2** — plugin auto-selects subtype; SpeedControl devices → Fan V2

---

## 0.2.17

- Camera thread exception fix — keep running regardless of single stream failures
- Move to explicit accessory subtypes per HomeKit device (Lightbulb, Lightbulb_switch, etc.)
- Simplified setter and deviceUpdated logic

---

## 0.2.16

- **Move Accessories to another Bridge** menu item — enables recovery if bridge was deleted
- Redo "Log all Devices" — shows missing and disabled bridge devices
- Fix for Lightbulb misspelling causing brightness issues
- Fix for RGB/Temperature lights all defaulting to Lightbulb type
- Fix for Saturation occasionally not being sent when value is 100

---

## 0.2.15

- Typo fix for Lightbulb → LightBulb
- Device selection screen refinements
- Continue device selection fine tuning — default to best guess type
- Bug fix for SecuritySpy camera image width
- Fix for restartBridge leftover from Device Bridge change

---

## 0.2.14

- Camera thread handling changes — start cameras when bridges activate
- Improved messaging for device add/delete operations

---

## 0.2.13

- Audio enable/disable selector for cameras (some streams fail if audio enabled)
- Show current device state value in state selector (when using Show All)
- Bug fix for empty string integer conversion for deleted device parsing
- Z-Wave / Hue Light testing improvements for RGB/Temperature lights
- Thermostat further testing and improvements
- Fix for Celsius/Fahrenheit temperature conversion — HomeKit lives in Celsius; converts non-C thermostats
- GitHub issue #12: Sanitise all device names to avoid unrecognised HomeKit crash
- Check for ports in use — use next available port

---

## 0.2.2

- Refactor device ID list for faster device update pathway
- Add **Debug Single Device** option in Plugin Config — select one device to trace

---

## 0.1.8

- Add **Smoke Sensor**
- Add **Leak Sensor**
- Add **Carbon Monoxide Sensor**
- Add **Luminance / Light Sensor** (with check for >100,000 lux values)

---

## 0.0.6

- Manage startup and shutdown of multiple threads, event loops, bridges, and drivers
- Bridges and all attached accessories, drivers, and threads start/stop correctly when device communication is enabled/disabled

---

## 0.0.4

- Add **HomeKit Bridge** device — enables unlimited devices via multiple bridges
- Beginning of device selection — cut down visible options to sensible choices
