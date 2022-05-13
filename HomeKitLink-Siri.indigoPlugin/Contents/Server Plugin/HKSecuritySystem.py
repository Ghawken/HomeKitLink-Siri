## HomeKit Devices

import logging

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import * # (CATEGORY_FAN,
                        # CATEGORY_LIGHTBULB,
                       #  CATEGORY_GARAGE_DOOR_OPENER,
                       #  CATEGORY_SENSOR)
from pyhap.const import (
    CATEGORY_CAMERA,
    CATEGORY_TARGET_CONTROLLER,
    CATEGORY_TELEVISION,
    HAP_REPR_VALUE,
    STANDALONE_AID,
)
from pyhap.const import (
    CATEGORY_FAUCET,
    CATEGORY_OUTLET,
    CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER,
    CATEGORY_SWITCH,
)

from HKConstants import *
import HKutils

logger = logging.getLogger("Plugin.HomeKitSpawn")
logger.setLevel(logging.DEBUG)

HK_ALARM_STAY_ARMED = 0
HK_ALARM_AWAY_ARMED = 1
HK_ALARM_NIGHT_ARMED = 2
HK_ALARM_DISARMED = 3
HK_ALARM_TRIGGERED = 4

PARADOX_TO_HOMEKIT_CURRENT = {
    "armed_home": HK_ALARM_STAY_ARMED,
    "armed_vacation": HK_ALARM_AWAY_ARMED,
    "armed_away": HK_ALARM_AWAY_ARMED,
    "armed_night": HK_ALARM_NIGHT_ARMED,
    "arming": HK_ALARM_DISARMED,
    "disarmed": HK_ALARM_DISARMED,
    "triggered": HK_ALARM_TRIGGERED,
}
PARADOX_TO_HOMEKIT_TARGET = {
    "armed_home": HK_ALARM_STAY_ARMED,
    "armed_vacation": HK_ALARM_AWAY_ARMED,
    "armed_away": HK_ALARM_AWAY_ARMED,
    "armed_night": HK_ALARM_NIGHT_ARMED,
    "arming": HK_ALARM_DISARMED,
    "disarmed": HK_ALARM_DISARMED
}
DSC_TO_HOMEKIT_CURRENT = {
    "armed": HK_ALARM_STAY_ARMED,
    "armed_stay":HK_ALARM_STAY_ARMED,
    "armed_away": HK_ALARM_AWAY_ARMED,
    "exitDelay": HK_ALARM_DISARMED,
    "disarmed": HK_ALARM_DISARMED,
    "tripped": HK_ALARM_TRIGGERED,
}
DSC_TO_HOMEKIT_TARGET = {
    "armed": HK_ALARM_STAY_ARMED,
    "armed_stay":HK_ALARM_STAY_ARMED,
    "armed_away": HK_ALARM_AWAY_ARMED,
    "exitDelay": HK_ALARM_DISARMED,
    "disarmed": HK_ALARM_DISARMED,
}
VSS_TO_HOMEKIT_CURRENT = {
    "0": HK_ALARM_STAY_ARMED,
    "1": HK_ALARM_AWAY_ARMED,
    "2": HK_ALARM_NIGHT_ARMED,
    "3": HK_ALARM_DISARMED,
    "4": HK_ALARM_TRIGGERED
}
VSS_TO_HOMEKIT_TARGET = {
    "0": HK_ALARM_STAY_ARMED,
    "1": HK_ALARM_AWAY_ARMED,
    "2": HK_ALARM_NIGHT_ARMED,
    "3": HK_ALARM_DISARMED
}

class SecuritySystem(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...
    category = CATEGORY_ALARM_SYSTEM

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):

        super().__init__( driver, plugin, indigodeviceid, display_name, aid)

        self.plugin = plugin
        self.SET_TO_USE_CURRENT = {}
        self.SET_TO_USE_TARGET = {}
        self.device_current_state = ""
        self.device_target_state = ""
        self.indigodeviceid = indigodeviceid
        device = indigo.devices[self.indigodeviceid]
        self.plugin_inuse  = device.pluginId
        if self.plugin_inuse == "com.perceptiveautomation.indigoplugin.vss":
            logger.debug("Setting VSS Conversion")
            self.SET_TO_USE_CURRENT = VSS_TO_HOMEKIT_CURRENT
            self.SET_TO_USE_TARGET = VSS_TO_HOMEKIT_TARGET
            self.device_current_state = "securitySystemState"
        elif self.plugin_inuse == "com.GlennNZ.indigoplugin.ParadoxAlarm":
            self.SET_TO_USE_CURRENT = PARADOX_TO_HOMEKIT_CURRENT
            self.SET_TO_USE_TARGET = PARADOX_TO_HOMEKIT_TARGET
            self.device_current_state = "Current_State"

        elif self.plugin_inuse == "com.frightideas.indigoplugin.dscAlarm":
            self.SET_TO_USE_CURRENT = DSC_TO_HOMEKIT_CURRENT
            self.SET_TO_USE_TARGET = DSC_TO_HOMEKIT_TARGET
            self.device_current_state = "state"

        serv_security = self.add_preload_service("SecuritySystem")

        currentstate = self.get_security()
        self.char_current_state = serv_security.configure_char( 'SecuritySystemCurrentState')  ## 3 == unknown at startup
        self.char_target_state = serv_security.configure_char("SecuritySystemTargetState", setter_callback=self.set_security )

        self.set_fromdeviceUpdate(device.states)


    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_security(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Security Values:{char_values}")

        # Given interfacing with plugins in this case - not indigo server/standard devices
        # Feel better to let this thread/async do all the communication.
        # Minus the device Update - which will have to be in plugin.py
        # self.plugin.Plugin_setter_callback(self, "securitySystem", char_values)
        # needs target to also be set..  probably let deviceUpdate do that for confirmation.
        try:
            indigodevice = indigo.devices[self.indigodeviceid]
            ## get temperature unit we are using
            basePlugin = indigo.server.getPlugin(self.plugin_inuse)
            logger.debug(f"Plugin in Use: {self.plugin_inuse}")
            if basePlugin.isEnabled():
                if self.plugin_inuse == "com.perceptiveautomation.indigoplugin.vss":
                    basePlugin.executeAction("setSecuritySystemState", deviceId=self.indigodeviceid, props={"securitySystemState": str(char_values)} )
                elif self.plugin_inuse == "com.GlennNZ.indigoplugin.ParadoxAlarm":
                    partition= indigodevice.globalProps["com.GlennNZ.indigoplugin.ParadoxAlarm"]["zonePartition"]
                    basePlugin.executeAction("controlAlarm", deviceId=self.indigodeviceid, props={"action": str(char_values), "partition": int(partition)})
                elif self.plugin_inuse == "com.frightideas.indigoplugin.dscAlarm":
                    if int(char_values) == HK_ALARM_DISARMED:
                        basePlugin.executeAction("actionDisarm", deviceId=self.indigodeviceid)
                    elif int(char_values) == HK_ALARM_STAY_ARMED:
                        basePlugin.executeAction("actionArmStay", deviceId=self.indigodeviceid)
                    elif int(char_values) == HK_ALARM_AWAY_ARMED:
                        basePlugin.executeAction("actionArmAway", deviceId=self.indigodeviceid)
                else:
                    logger.info("Unsupported Security System Plugin.  Sorry.  Maybe on a TODO list somewhere..")
            else:
                logger.info(f"HomeKit tried to control Device but {self.plugin_inuse} Plugin is not enabled.")

        except:
            logger.exception("Caught Exception in set_Security System, HKDevice side")

    def set_fromdeviceUpdate(self, states):
        try:
            if self.plugin.debug6:
                logger.debug(f"set_from device Update called by deviceUpdate with value:{states}")

            if self.device_current_state in states:
                currentstate = states[self.device_current_state]
                targetstate = states[self.device_current_state]
            if self.plugin.debug6:
                logger.debug(f"New CurrentState == {currentstate}, and TargetState == {targetstate}")

            if (currentstate := self.SET_TO_USE_CURRENT.get(currentstate)) is not None:
                self.char_current_state.set_value(currentstate)
                if self.plugin.debug6:
                    logger.debug(f"Confirmed.  Current state set to {currentstate}")

            if (targetstate := self.SET_TO_USE_TARGET.get(targetstate)) is not None:
                self.char_target_state.set_value(targetstate)
                if self.plugin.debug6:
                    logger.debug(f"Confirmed. Target state set to {targetstate}")
        except:
            logger.exception("set from deviceUpdate exception")

    def get_security(self):
        try:
            logger.debug("get_Security Called")
            indigodevice = indigo.devices[self.indigodeviceid]

            if self.plugin_inuse in ( "com.perceptiveautomation.indigoplugin.vss","com.GlennNZ.indigoplugin.ParadoxAlarm"):
                logger.debug(f"Using VSS and ParadoxAlarm, and device_current_state == {self.device_current_state}")
                if str(self.device_current_state) in indigodevice.states:
                    #logger.debug(f"IndigoDevice\n {indigodevice.states}")
                    state = indigodevice.states[str(self.device_current_state)]
                    value = self.SET_TO_USE_CURRENT.get(state)
                    logger.debug(f"Returning value of {value}, using state of {state}")

            elif self.plugin_inuse == "com.frightideas.indigoplugin.dscAlarm":
                logger.debug("Using dscAlarm")
                if "state" in indigodevice.states:
                    state = indigodevice.states["state"]
                    if indigodevice.states["ArmedState.disarmed"]:
                        value = self.SET_TO_USE_CURRENT.get(state)
                    elif indigodevice.states["ArmedState.away"]:
                        state= state+"_away"
                        value = self.SET_TO_USE_CURRENT.get(state)
                    elif indigodevice.states["ArmedState.stay"]:
                        state= state+"_stay"
                        value = self.SET_TO_USE_CURRENT.get(state)
                    else:
                        value = self.SET_TO_USE_CURRENT.get(state)
            else:
                value = HK_ALARM_DISARMED

            if value == None:
                ## empty states, not running plugins etc.
                logger.debug("value returned None, setting to Disarmed.")
                value = 3

            if self.plugin.debug6:
                logger.debug(f"Set in Use:\n {self.SET_TO_USE_CURRENT}")
                logger.debug(f"get_security: Plugin {self.plugin_inuse}: Took State {state} and converted to value {value}")
            return value
        except:
            logger.exception("Caught exception in get_security HK device side")