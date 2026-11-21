"""A camera's control device: a gate, door or light shown inside the camera's own HomeKit accessory.

Optional on every camera type (Blue Iris, SecuritySpy, UniFi Protect). The control is an Indigo device
or action group, shown as a Lock (Home asks for Face ID / an unlocked phone before opening) or a Switch.

- Lock follows Indigo's lock convention: device on = locked, off = unlocked (Indigo locks, UniFi Access
  doors). Unlock turns the device off, lock turns it on.
- Switch: on turns the device on, off turns it off.
- Momentary (default): HomeKit shows unlocked / on for a few seconds, then locked / off again. The device
  does its own pulse or relock (e.g. a UniFi Access door's momentary unlock, a relay with auto-off, or an
  action group). Action groups are always momentary.
- Follows the device: HomeKit shows the device's on/off state.

The same approach as homebridge-unifi-protect's Access lock on Protect cameras.
"""

import logging
import threading

try:
    import indigo
except ImportError:
    pass

_LOGGER = logging.getLogger("Plugin.HomeKitSpawn")

LOCK_UNSECURED = 0
LOCK_SECURED = 1


def control_settings(dev):
    """The camera's control settings, or None if it has no control device."""
    props = dev.pluginProps
    try:
        control_id = int(props.get("HomeKit_controlDevice", "") or 0)
    except (TypeError, ValueError):
        return None
    if control_id <= 0 or control_id == dev.id:
        return None
    try:
        seconds = float(props.get("HomeKit_controlSeconds", "") or 3)
    except (TypeError, ValueError):
        seconds = 3
    return {"id": control_id,
            "kind": "switch" if props.get("HomeKit_controlType", "lock") == "switch" else "lock",
            "follow": props.get("HomeKit_controlMode", "momentary") == "follow",
            "seconds": min(max(seconds, 1), 60),
            "name": str(props.get("HomeKit_controlName", "") or "").strip()}


def add_control(accessory, plugin, camera_id):
    """Add the Lock or Switch service to a camera accessory (call in the camera's __init__)."""
    accessory.control = None
    try:
        dev = indigo.devices[camera_id]
    except Exception:
        return
    settings = control_settings(dev)
    if settings is None:
        return
    try:
        target = indigo.actionGroups[settings["id"]] if settings["id"] in indigo.actionGroups else indigo.devices[settings["id"]]
    except Exception:
        plugin.logger.warning("[{}] its control device (id {}) no longer exists - choose another in the bridge settings".format(dev.name, settings["id"]))
        return
    settings["action_group"] = isinstance(target, indigo.ActionGroup)
    if settings["action_group"] or "onOffState" not in getattr(target, "states", {}):
        settings["follow"] = False   ## nothing to follow: always momentary
    name = settings["name"] or target.name
    settings["timer"] = None
    if settings["kind"] == "lock":
        serv = accessory.add_preload_service("LockMechanism", ["Name", "ConfiguredName"])
        serv.configure_char("Name", value=name)
        serv.configure_char("ConfiguredName", value=name)   ## the name the Home app shows for a second service
        settings["current"] = serv.configure_char("LockCurrentState", value=LOCK_SECURED)
        settings["target"] = serv.configure_char("LockTargetState", value=LOCK_SECURED)
    else:
        serv = accessory.add_preload_service("Switch", ["Name", "ConfiguredName"])
        serv.configure_char("Name", value=name)
        serv.configure_char("ConfiguredName", value=name)   ## the name the Home app shows for a second service
        settings["current"] = None
        settings["target"] = serv.configure_char("On", value=False)
    settings["target"].setter_callback = lambda value: _set_from_homekit(accessory, plugin, value)
    accessory.control = settings
    if settings["follow"]:
        update_from_device(accessory, target)
    plugin.logger.info("[{}] control: '{}' as a {}, {}".format(
        dev.name, name, settings["kind"],
        "follows the device" if settings["follow"] else "momentary ({:g} s)".format(settings["seconds"])))


def _show(control, opened):
    """Show opened (unlocked / on) or closed (locked / off) in HomeKit."""
    if control["kind"] == "lock":
        value = LOCK_UNSECURED if opened else LOCK_SECURED
        control["target"].set_value(value)
        control["current"].set_value(value)
    else:
        control["target"].set_value(bool(opened))


def _set_from_homekit(accessory, plugin, value):
    control = accessory.control
    opened = (value == LOCK_UNSECURED) if control["kind"] == "lock" else bool(value)
    try:
        if control["action_group"]:
            if not opened:   ## an action group only opens; the tile closes by itself
                if control["timer"] is None:
                    _show(control, False)
                return
            plugin.logger.info("HomeKit control: running action group '{}'".format(indigo.actionGroups[control["id"]].name))
            indigo.actionGroup.execute(control["id"])
        else:
            dev = indigo.devices[control["id"]]
            if not control["follow"] and not opened and control["timer"] is not None:
                return   ## closing during the momentary window: it closes by itself
            turn_on = (not opened) if control["kind"] == "lock" else opened   ## lock: on = locked
            plugin.logger.info("HomeKit control: {} '{}'".format(
                ("unlocking" if opened else "locking") if control["kind"] == "lock" else ("turning on" if opened else "turning off"), dev.name))
            if turn_on:
                indigo.device.turnOn(control["id"])
            else:
                indigo.device.turnOff(control["id"])
    except Exception:
        plugin.logger.exception("HomeKit control: couldn't run the camera's control device")
        _show(control, False)
        return
    if control["follow"]:
        if control["kind"] == "lock":
            control["current"].set_value(LOCK_UNSECURED if opened else LOCK_SECURED)   ## the device's update confirms it
        return
    if opened:
        _show(control, True)   ## Protect-style: shows opened at once (a lock otherwise sits on "Unlocking")
        if control["timer"] is not None:
            control["timer"].cancel()
        timer = threading.Timer(control["seconds"], _momentary_done, args=(control,))
        timer.daemon = True
        control["timer"] = timer
        timer.start()


def _momentary_done(control):
    control["timer"] = None
    try:
        _show(control, False)
    except Exception:
        _LOGGER.debug("camera control reset failed", exc_info=True)


def update_from_device(accessory, dev):
    """The control device changed in Indigo: show it (follow mode only)."""
    control = getattr(accessory, "control", None)
    if not control or not control["follow"] or "onOffState" not in dev.states:
        return
    on = bool(dev.states["onOffState"])
    opened = (not on) if control["kind"] == "lock" else on
    if control["kind"] == "lock":
        value = LOCK_UNSECURED if opened else LOCK_SECURED
        if control["current"].value != value:
            control["current"].set_value(value)
        if control["target"].value != value:
            control["target"].set_value(value)
    elif control["target"].value != opened:
        control["target"].set_value(opened)
