## HomeKit Devices


import logging
import math

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

logger = logging.getLogger("Plugin.HomeKitSpawn")

from HKConstants import *

import HKutils

#import HKDevicesCamera



class TemperatureSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        batteryLevel = None
        self._unit =TEMP_CELSIUS
        indigodevice = indigo.devices[indigodeviceid]
        ## get temperature unit we are using
        tempSelector = indigodevice.pluginProps.get("HomeKit_tempSelector", False)  ## True if F
        if tempSelector:
            logger.debug("{} Unit Selected".format(TEMP_FAHRENHEIT))
            self._unit = TEMP_FAHRENHEIT
        else:
            logger.debug("{} unit Selected".format(TEMP_CELSIUS))
            self._unit = TEMP_CELSIUS

        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('TemperatureSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )

        self.char_temp = serv_temp.configure_char('CurrentTemperature',  getter_callback=self.get_temp)
        # Display units characteristic

        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    def _temperature_to_homekit(self, temp):
        return HKutils.temperature_to_homekit(temp, self._unit)

    def set_temperature(self, temperature):
        if self.plugin.debug6:
            logger.debug(f"Updating Temp: {temperature} and setting Converted value {self._temperature_to_homekit(temperature)}")
        self.char_temp.set_value(self._temperature_to_homekit(temperature))

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Temperature Sensor - run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "temperature")
        return self._temperature_to_homekit(HKutils.convert_to_float(value))

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class LightSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])


        serv_temp = self.add_preload_service('LightSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_temp = serv_temp.configure_char('CurrentAmbientLightLevel',  getter_callback=self.get_sensor)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Light Level Sensor - run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_sensor(self):
        value = self.plugin.Plugin_getter_callback(self, "LightLevel")
        return HKutils.convert_to_float(value)

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class CarbonDioxideSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('CarbonDioxideSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_on = serv_temp.configure_char('CarbonDioxideDetected',  getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Carbon Dixoide Sensor Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_temp(self, value):  ## no point as doesnt set
        if self.plugin.debug6:
            logger.debug("Temperature value: {}".format(value))
        #self.plugin.Plugin_setter_callback(self, "temperature", value)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "SensorCarbonDioxide")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class CarbonMonoxideSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(states["batteryLevel"])

        serv_temp = self.add_preload_service('CarbonMonoxideSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2)
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_on = serv_temp.configure_char('CarbonMonoxideDetected',  getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_temp(self, value):  ## no point as doesnt set
        if self.plugin.debug6:
            logger.debug("Temperature value: {}".format(value))
        #self.plugin.Plugin_setter_callback(self, "temperature", value)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "SensorCarbonMonoxide")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")


class LeakSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid, display_name, aid):  # self, *args, **kwargs):
        super().__init__(driver, plugin, indigodeviceid, display_name, aid)  # *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('LeakSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2)
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_on = serv_temp.configure_char('LeakDetected', getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "SensorLeak")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class GenericSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('TemperatureSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2)
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_temp = serv_temp.configure_char('CurrentTemperature',  getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "genericSensor")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class HumiditySensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None
        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('HumiditySensor')
        ## leave this as char_temp -- would make more sense to change all to char_setdevicevalue or something similiar
        ## but basically deviceupdated should be same for both temp and humidity - so in deviceupdate can call char_temp.setvalue
        # for both temperature device and humidity device and should be fine.
        # will need to test values..

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )

        self.char_temp = serv_temp.configure_char('CurrentRelativeHumidity',  getter_callback=self.get_humid)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_humid(self):
        value = self.plugin.Plugin_getter_callback(self, "humidity")
        return HKutils.convert_to_float(value)

    def _set_chars(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class SmokeSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('SmokeSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        #      "ValidValues": {
       #  "OccupancyDetected": 1,
       #  "OccupancyNotDetected": 0
        # }
        self.char_on = serv_temp.configure_char('SmokeDetected', getter_callback=self.get_sensor)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_sensor(self):
        value = self.plugin.Plugin_getter_callback(self, "sensorSmoke")
        if type(value) == bool:
            if value:  ##convert boolen to
                value = 1
            else:
                value = 0
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class OccupancySensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('OccupancySensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2)
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        #      "ValidValues": {
       #  "OccupancyDetected": 1,
       #  "OccupancyNotDetected": 0
        # }
        self.char_on = serv_temp.configure_char('OccupancyDetected', getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "sensorOccupancy")
        if type(value) == bool:
            if value:  ##convert boolen to
                value = 1
            else:
                value = 0
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class ContactSensor(Accessory):
    """Sensor Pushing results if changed"""

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('ContactSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2)
            is_low_battery = 1 if batteryLevel < self.plugin.low_battery_threshold else 0
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=is_low_battery   )


        self.char_on = serv_temp.configure_char('ContactSensorState',  getter_callback=self.get_temp)
        serv_temp.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_temp(self):
        value = self.plugin.Plugin_getter_callback(self, "sensorContactSensor")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class Fanv2(Accessory):
    category = CATEGORY_FAN
    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)

        # Add the fan service. Also add optional characteristics to it.
        serv_fan = self.add_preload_service('Fanv2', chars=['RotationSpeed', 'RotationDirection', "SwingMode"])

        self.char_on = serv_fan.configure_char('Active', getter_callback=self.on_getter)
        self.char_rotation_speed = serv_fan.configure_char( 'RotationSpeed')
        self.char_rotation_direction = serv_fan.configure_char( 'RotationDirection')
        self.char_swing_mode = serv_fan.configure_char("SwingMode")
        serv_fan.setter_callback = self._set_chars

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def on_setter(self, value):
        if self.plugin.debug6:
            logger.debug("On Setter Event:")
        self.plugin.Plugin_setter_callback(self,"onOffState", value)

    def on_getter(self):
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value  # turn on

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")
## if either send both as need to manage one or both as can
        if "Active" in char_values or "RotationSpeed" in char_values:
            if self.plugin.debug6:
                logger.debug('Active / or RotationSpeed changed to: {}, sending to Indigo'.format( char_values))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)

class FanSimple(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_FAN

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)
        serv_switch = self.add_preload_service('Fan')
        self.char_on = serv_switch.configure_char( 'On', value=False, getter_callback=self.get_switch)
        serv_switch.setter_callback = self.set_switch ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only. == Action Groups"""
        return self.plugin.check_activateOnly(deviceid)

    def set_switch(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Fan Values:{char_values}")
        if self.activate_only and char_values["On"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is True False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(False)

    def get_switch(self):
        if self.activate_only:
            return False
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value

class Fan_old(Accessory):

    category = CATEGORY_FAN
    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        # Add the fan service. Also add optional characteristics to it.
        serv_fan = self.add_preload_service('Fanv2', chars=['RotationSpeed', 'RotationDirection'])
        self.char_on = serv_fan.configure_char('On', getter_callback=self.on_getter)
        self.char_rotation_speed = serv_fan.configure_char( 'RotationSpeed')
        self.char_rotation_direction = serv_fan.configure_char( 'RotationDirection')
   #     self.char_swing_mode = serv_fan.configure_char("SwingMode")
        serv_fan.setter_callback = self._set_chars

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def on_setter(self, value):
        if self.plugin.debug6:
            logger.debug("On Setter Event:")
        self.plugin.Plugin_setter_callback(self,"onOffState", value)

    def on_getter(self):
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value  # turn on

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

        if "On" in char_values or "Brightness" in char_values:
            if self.plugin.debug6:
                logger.debug('On / or Brightness changed to: {}, sending to Indigo'.format( char_values))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)

        if "Hue" in char_values:
            if self.plugin.debug6:
                logger.debug('Hue changed to: {} '.format( char_values["Hue"]))
            self.plugin.Plugin_setter_callback(self, "Hue", char_values)

class LightBulb(Accessory):
## really use a switch displayed as light bulb
    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        serv_light = self.add_preload_service('Lightbulb')
        self.char_on = serv_light.configure_char( 'On',  getter_callback=self.get_bulb)
        serv_light.setter_callback = self._set_chars  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_bulb(self):
        #if self.plugin.debug6:
          #  logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

        if "On" in char_values or "Brightness" in char_values:
            if self.plugin.debug6:
                logger.debug('On / or Brightness changed to: {}, sending to Indigo'.format( char_values))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)

        if "Hue" in char_values:
            if self.plugin.debug6:
                logger.debug('Hue changed to: {} '.format( char_values["Hue"]))
            self.plugin.Plugin_setter_callback(self, "Hue", char_values)




class SwitchSimple(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_SWITCH

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)
        serv_switch = self.add_preload_service('Switch')
        self.char_on = serv_switch.configure_char( 'On', value=False, getter_callback=self.get_switch)#, setter_callback=self.set_switch ) #setter_callback=self.set_bulb,
        serv_switch.setter_callback = self.set_switch ## Setter for everything

    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_switch(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Switch Values:{char_values}")
       # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["On"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(False)

    def get_switch(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            #logger.debug("Active Only switch setting to False")
            return False
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value


    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")


class Valve(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_SPRINKLER

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)

        serv_valve = self.add_preload_service('Valve')
        self.char_on = serv_valve.configure_char( 'Active', value=False, getter_callback=self.get_valve)
        self.char_in_use = serv_valve.configure_char('InUse', value=False )
        self.char_valve_type = serv_valve.configure_char( "ValveType", value=0)
        serv_valve.setter_callback = self.set_valve ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_valve(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Outlet Values:{char_values}")
       # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["Active"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(0)
            self.char_in_use.set_value(0)
        else:
            self.char_in_use.set_value(char_values["Active"])

    def get_valve(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            return 0
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
       # logger.debug("get_valve value:{}".format(value))
        if value:
            return 1
        elif value==False:
            return 0

         # "Genericvalve": 0,
         # "Irrigation": 1,
         # "Showerhead": 2,
         # "Waterfaucet": 3

class Irrigation(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_SPRINKLER

    def __init__(self, driver, plugin, indigodeviceid, display_name, aid):
        super().__init__(driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)

        serv_valve = self.add_preload_service('Valve')
        self.char_on = serv_valve.configure_char('Active', value=False, getter_callback=self.get_valve)
        self.char_in_use = serv_valve.configure_char('InUse', value=False)
        self.char_valve_type = serv_valve.configure_char("ValveType", value=1)
        serv_valve.setter_callback = self.set_valve  ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_valve(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Outlet Values:{char_values}")
        # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["Active"] == 0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        # value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only:  ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(0)
            self.char_in_use.set_value(0)
        else:
            self.char_in_use.set_value(char_values["Active"])

    def get_valve(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            return 0
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        # logger.debug("get_valve value:{}".format(value))
        if value:
            return 1
        elif value == False:
            return 0

class Showerhead(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_SHOWER_HEAD

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)

        serv_valve = self.add_preload_service('Valve')
        self.char_on = serv_valve.configure_char( 'Active', value=False, getter_callback=self.get_valve)
        self.char_in_use = serv_valve.configure_char('InUse', value=False )
        self.char_valve_type = serv_valve.configure_char( "ValveType", value=2)
        serv_valve.setter_callback = self.set_valve ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_valve(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Outlet Values:{char_values}")
       # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["Active"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(0)
            self.char_in_use.set_value(0)
        else:
            self.char_in_use.set_value(char_values["Active"])

    def get_valve(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            return 0
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
       # logger.debug("get_valve value:{}".format(value))
        if value:
            return 1
        elif value==False:
            return 0

         # "Genericvalve": 0,
         # "Irrigation": 1,
         # "Showerhead": 2,
         # "Waterfaucet": 3

class Faucet(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_FAUCET

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)

        serv_valve = self.add_preload_service('Valve')
        self.char_on = serv_valve.configure_char( 'Active', value=False, getter_callback=self.get_valve)
        self.char_in_use = serv_valve.configure_char('InUse', value=False )
        self.char_valve_type = serv_valve.configure_char( "ValveType", value=3)
        serv_valve.setter_callback = self.set_valve ## Setter for everything

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_valve(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Outlet Values:{char_values}")
       # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["Active"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(0)
            self.char_in_use.set_value(0)
        else:
            self.char_in_use.set_value(char_values["Active"])

    def get_valve(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            return 0
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
       # logger.debug("get_valve value:{}".format(value))
        if value:
            return 1
        elif value==False:
            return 0

         # "Genericvalve": 0,
         # "Irrigation": 1,
         # "Showerhead": 2,
         # "Waterfaucet": 3

class Outlet(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_OUTLET

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        self.activate_only = self.is_activate(indigodeviceid)
        serv_outlet = self.add_preload_service('Outlet',chars=["On", "OutletInUse"])
        self.char_on = serv_outlet.configure_char( 'On', value=False, getter_callback=self.get_switch)#, setter_callback=self.set_switch ) #setter_callback=self.set_bulb,
        self.char_outlet_in_use = serv_outlet.configure_char('OutletInUse', value=True )
        serv_outlet.setter_callback = self.set_switch ## Setter for everything

    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    def set_switch(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Outlet Values:{char_values}")
       # logger.debug("Switch value: %s", value)
        if self.activate_only and char_values["On"]==0:
            if self.plugin.debug6:
                logger.debug("DeviceId: {}: Ignoring turn_off call as activate_only".format(self.indigodeviceid))
            return
        #value is Ture False here not a list
        self.plugin.Plugin_setter_callback(self, "onOffState", char_values)
        ## then set switch to False if activate only
        if self.activate_only: ## Doesn't matter On or OFF is activate only, acbove has been run and then seto off immediatelly./ and char_values["On"]==0:
            self.char_on.set_value(False)

    def get_switch(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            #logger.debug("Active Only Outlet setting to False")
            return False
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value


    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

class HueLightBulb(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        indigodevice = indigo.devices[indigodeviceid]

        supportsRGB = indigodevice.supportsRGB
        supportsWhiteTemperature = indigodevice.supportsWhiteTemperature
        chars_to_use =  ["On","Brightness", "Hue", "Saturation"]
        cancelWhiteTemp = False

        # no longer an issue if use RGB for colour states for Hue.  Which have done.
        # Leave here
        # if "manufacturerName" in indigodevice.states:
        #     if "Signify" in indigodevice.states["manufacturerName"]:
        #         ## cancel Hue plugin bulbs - white temp still works just using rgb bulbs as recommended
        #         cancelWhiteTemp = True##
        #         ## delte below testing onluyTODO
        #         cancelWhiteTemp = False
        #         ##
        #         if self.plugin.debug6:
        #             logger.debug("Hue Plugin Bulb found, cancelling separate Color Temperature.  Device {}".format(indigodevice.name))

        if supportsWhiteTemperature==True and cancelWhiteTemp != True:
            chars_to_use.append("ColorTemperature")

        serv_light = self.add_preload_service('Lightbulb', chars=chars_to_use)
        self.char_on = serv_light.configure_char( 'On',  getter_callback=self.get_bulb ) #setter_callback=self.set_bulb,
        self.Hue = serv_light.configure_char('Hue',  getter_callback=self.get_hue)
        self.Brightness = serv_light.configure_char('Brightness', getter_callback=self.get_brightness ) #,  #setter_callback=self.set_brightness,)
        self.Saturation = serv_light.configure_char('Saturation' , getter_callback=self.get_saturation)
        # add color temperature
        # likely to need first info pull on indigo - will only be on startup

        if "ColorTemperature" in chars_to_use:
            self.char_color_temp = serv_light.configure_char(
                "ColorTemperature",
                value=math.floor(153),
                properties={
                    "minValue": math.floor(85),  ## iobviously when using default - floor not needed - but will see if can adjust later
                    "maxValue": math.floor(780),
                },
            )

        ## remove unneccesary self
        serv_light.setter_callback = self._set_chars  ## Setter for everything


    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_bulb(self, value):
       # if self.plugin.debug6:
         #   logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "onOffState", value)

    def get_bulb(self):
       # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value

    def set_hue(self, value):
       # logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "Hue", value)

    def get_hue(self):
       # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "Hue")
        return value

    def set_brightness(self, value):
        # logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "Brightness", value)

    def get_brightness(self):
        # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "Brightness")
        return value

    def set_saturation(self, value):
        # logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "Saturation", value)

    def get_saturation(self):
       # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "Saturation")
        return value

    def _get_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Get Chars{char_values}")

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

        if "On" in char_values or "Brightness" in char_values:
            if self.plugin.debug6:
                logger.debug('On / or Brightness changed to: {}, sending to Indigo'.format( char_values))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)  ## probably shoudl check ?senmd
            ## ignore brightness
        if "Hue" in char_values:
            if self.plugin.debug6:
                logger.debug('Hue changed to: {} '.format( char_values["Hue"]))
            self.plugin.Plugin_setter_callback(self, "Hue", char_values)
        if "ColorTemperature" in char_values:
            if self.plugin.debug6:
                logger.debug('ColorTemperature changed to: {} '.format( char_values["ColorTemperature"]))
            self.plugin.Plugin_setter_callback(self, "ColorTemperature", char_values)


class DimmerBulb(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):

        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        serv_light = self.add_preload_service('Lightbulb', chars=["On", "Brightness"])
        self.char_on = serv_light.configure_char( 'On',  getter_callback=self.get_bulb ) #setter_callback=self.set_bulb,
        #self.Hue = serv_light.configure_char('Hue',  getter_callback=self.get_hue)
        self.Brightness = serv_light.configure_char('Brightness', getter_callback=self.get_brightness ) #,  #setter_callback=self.set_brightness,)
        #self.Saturation = serv_light.configure_char('Saturation' , getter_callback=self.get_saturation)
        ## remove unneccesary self
        serv_light.setter_callback = self._set_chars  ## Setter for everything


    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    async def run(self):
        if self.plugin.debug6:
            logger.debug("DimmerBulb Accessory stareted: Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_bulb(self, value):
       # if self.plugin.debug6:
         #   logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "onOffState", value)

    def get_bulb(self):
       # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "onOffState")
        return value

    def set_brightness(self, value):
        # logger.debug("Bulb value: %s", value)
        self.plugin.Plugin_setter_callback(self, "Brightness", value)

    def get_brightness(self):
        # logger.debug("Bulb value: %s", value)
        value = self.plugin.Plugin_getter_callback(self, "Brightness")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

        if "On" in char_values or "Brightness" in char_values:
            if self.plugin.debug6:
                logger.debug('On / or Brightness changed to: {}, sending to Indigo'.format( char_values))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)  ## probably shoudl check ?senmd
            ## ignore brightness if On present


class Lock(Accessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...
    category = CATEGORY_DOOR_LOCK

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        serv_lock = self.add_preload_service("LockMechanism")
        self.char_current_state = serv_lock.configure_char( 'LockCurrentState', value=3 , getter_callback=self.get_lock)  ## 3 == unknown at startup
        self.char_target_state = serv_lock.configure_char("LockTargetState", setter_callback=self.set_lock, getter_callback=self.get_lock)
        #serv_lock.setter_callback = self.set_lock ## Setter for everything
        # Only set target state not current... see if fixes unlocking
    ##
    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def set_lock(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Set Lock Values:{char_values}")
        self.plugin.Plugin_setter_callback(self, "lockState", char_values)
        ## correct onOffState to get, not for set
        ##

    def get_lock(self):
        value = self.plugin.Plugin_getter_callback(self, "lockState")
        return value

class GarageDoor(Accessory):

    category = CATEGORY_GARAGE_DOOR_OPENER

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)

        self.activate_only = self.is_activate(indigodeviceid)

        serv_garage_door = self.add_preload_service("GarageDoorOpener")
        self.char_current_state = serv_garage_door.configure_char(
            "CurrentDoorState", value=0 )# getter_callback=self.get_state)

        self.char_target_state = serv_garage_door.configure_char(
            "TargetDoorState", value=0, setter_callback=self._set_chars
        )
        # self.char_obstruction_detected = serv_garage_door.configure_char(
        #     "ObstructionDeteced", value=False
        # )
        # Could be like Doorbell and Camera - obstruction sensor - except this type Sensor True/False
        # TODO add support - will need config changes/menu

        # add state from start and set.
        currentstate = self.get_state()
        if currentstate is not None:
            self.char_target_state.set_value(currentstate)
            self.char_current_state.set_value(currentstate)

        serv_garage_door.setter_callback = self._set_chars  ## Setter for everything

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_state(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            #logger.debug("Active Only switch setting to False")
            return False
        value = self.plugin.Plugin_getter_callback(self, "garageDoorState")
        return value

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"_Set_Chars received : {char_values}")
        #{'TargetDoorState': 0}
        # but also receiving a integer value 1 or 0
        # Odd Here we seem to get a 0 or a 1 alone, then followed immediately by a dict with TargetDoorState and the same 1 or 0
        # No other item is set up to be a setter...  no sure whether this is my error, library feature or library bug
        # Check is a dict and ignore the random integer value being received.
        # also slightly naughty here changing TargetDoorState to a On state and sending to Onoffstate pathway
        #
        if isinstance(char_values,dict):
            if "TargetDoorState" in char_values:
                if self.plugin.debug6:
                    logger.debug('TargetDoorState wished to be {}, converted to and sending to Indigo'.format( char_values))
                char_values["On"] = char_values.pop("TargetDoorState")  ## replace targetdoorstate with On and send through onOffRelay actioning..
                if self.plugin.debug6:
                    logger.debug("Char Values converted from TargetDoorState to On/off.  New char_values : {}".format(char_values))
                self.plugin.Plugin_setter_callback(self, "onOffState", char_values)  ## probably shoudl check ?senmd

class WindowCovering(Accessory):

    category = CATEGORY_WINDOW_COVERING

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)

        self.activate_only = self.is_activate(indigodeviceid)
        indigodevice = indigo.devices[indigodeviceid]

        self._inverse = False
        ## get temperature unit we are using
        inverseSelector = indigodevice.pluginProps.get("HomeKit_inverseSelector", False)  ## True if F
        if inverseSelector:
            logger.debug("Inverse Controls Enabled. Inverse Selection: {}".format(inverseSelector))
            self._inverse = True
        else:
            logger.debug("Inverse Controls Not enabled. Inverse Selection:  {}".format(inverseSelector))
            self._inverse = False

        serv_window_covering = self.add_preload_service("WindowCovering")

        self.char_current_position = serv_window_covering.configure_char(
            "CurrentPosition", value=0 )# getter_callback=self.get_state)

        self.char_target_position  = serv_window_covering.configure_char(
            "TargetPosition", value=0, setter_callback=self._set_chars
        )
        self.char_position_state = serv_window_covering.configure_char(
            "PositionState", value=2
        )

        # add state from start and set.
        currentstate = self.get_state()
        if currentstate is not None:
            self.char_target_position.set_value(currentstate)
            self.char_current_position.set_value(currentstate)

        serv_window_covering.setter_callback = self._set_chars  ## Setter for everything

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_state(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            #logger.debug("Active Only switch setting to False")
            return False

        ## use tuple here
        brightness,onOffStatevalue = self.plugin.Plugin_getter_callback(self, "windowCovering")

        if brightness is not None:
            if self._inverse == False:
                brightness = brightness
            else:
                brightness =  100 - brightness
            return brightness
        else:  ## onOffState
            if onOffStatevalue is not None:
                if self._inverse == False:
                    if onOffStatevalue:
                        brightness = 100
                    else:
                        brightness = 0
                else:
                    if onOffStatevalue:
                        brightness = 0
                    else:
                        brightness = 100
                return brightness

    def set_covering_state(self, brightness, onOffStatevalue):
        if self.plugin.debug6:
            logger.debug("Blind: set covering state called with values {}, onOffState {}, and inverse {}".format(brightness, onOffStatevalue, self._inverse))
        if brightness is not None:
            if self._inverse == False:
                self.char_target_position.set_value(brightness)
                self.char_current_position.set_value(brightness)
            else:
                brightness =  100 - brightness
                self.char_target_position.set_value(brightness)
                self.char_current_position.set_value(brightness)
        else:  ## onOffState
            if onOffStatevalue is not None:
                if self._inverse == False:
                    if onOffStatevalue:
                        self.char_target_position.set_value(100)
                        self.char_current_position.set_value(100)
                    else:
                        self.char_target_position.set_value(0)
                        self.char_current_position.set_value(0)
                else:
                    if onOffStatevalue:
                        self.char_target_position.set_value(0)
                        self.char_current_position.set_value(0)
                    else:
                        self.char_target_position.set_value(100)
                        self.char_current_position.set_value(100)

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Blind: _set_Chars received : {char_values}")

        if isinstance(char_values,dict):
            if "TargetPosition" in char_values:
                if self.plugin.debug6:
                    logger.debug('TargetPosition wished to be {}, converted to and sending to Indigo'.format( char_values))
                if self._inverse == False:
                    if int(char_values['TargetPosition']) == 0:
                        char_values["On"] = 0
                    elif int(char_values["TargetPosition"]) == 100:
                        char_values['On'] = 1
                    char_values["Brightness"] = char_values.pop("TargetPosition")  ## replace targetdoorstate with On and send through onOffRelay actioning..
                    if self.plugin.debug6:
                        logger.debug("Char Values converted from TargetPosition to Brightness.  New char_values : {}".format(char_values))
                else:
                    if int(char_values['TargetPosition']) == 100:
                        char_values["On"] = 0
                    elif int(char_values["TargetPosition"]) == 0:
                        char_values['On'] = 1
                    char_values["Brightness"] = char_values.pop("TargetPosition")
                    char_values["Brightness"] = int(100 - char_values["Brightness"])
                    ## replace targetdoorstate with On and send through onOffRelay actioning..
                    if self.plugin.debug6:
                        logger.debug("Inverse: Char Values converted from TargetPosition to Brightness.  New char_values : {}".format(char_values))

                self.plugin.Plugin_setter_callback(self, "onOffState", char_values)  ## probably shoudl check ?senmd

class Window(Accessory):

    category = CATEGORY_WINDOW

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)

        self.activate_only = self.is_activate(indigodeviceid)
        indigodevice = indigo.devices[indigodeviceid]

        self._inverse = False
        ## get temperature unit we are using
        inverseSelector = indigodevice.pluginProps.get("HomeKit_inverseSelector", False)  ## True if F
        if inverseSelector:
            logger.debug("Inverse Controls Enabled. Inverse Selection: {}".format(inverseSelector))
            self._inverse = True
        else:
            logger.debug("Inverse Controls Not enabled. Inverse Selection:  {}".format(inverseSelector))
            self._inverse = False

        serv_window_covering = self.add_preload_service("Window")

        self.char_current_position = serv_window_covering.configure_char(
            "CurrentPosition", value=0 )# getter_callback=self.get_state)

        self.char_target_position  = serv_window_covering.configure_char(
            "TargetPosition", value=0, setter_callback=self._set_chars
        )
        self.char_position_state = serv_window_covering.configure_char(
            "PositionState", value=2
        )

        # add state from start and set.
        currentstate = self.get_state()
        if currentstate is not None:
            self.char_target_position.set_value(currentstate)
            self.char_current_position.set_value(currentstate)

        serv_window_covering.setter_callback = self._set_chars  ## Setter for everything

    def is_activate(self, deviceid):
        """Check if entity is activate only."""
        return self.plugin.check_activateOnly(deviceid)
        # check for absence of onOffState or whether active group - probably reverse logic

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Window: Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def get_state(self):
        # logger.debug("Bulb value: %s", value)
        if self.activate_only:
            #logger.debug("Active Only switch setting to False")
            return False

        ## use tuple here
        brightness,onOffStatevalue = self.plugin.Plugin_getter_callback(self, "windowAlone")

        if brightness is not None:
            if self._inverse == False:
                brightness = brightness
            else:
                brightness =  100 - brightness
            return brightness
        else:  ## onOffState
            if onOffStatevalue is not None:
                if self._inverse == False:
                    if onOffStatevalue:
                        brightness = 100
                    else:
                        brightness = 0
                else:
                    if onOffStatevalue:
                        brightness = 0
                    else:
                        brightness = 100
                return brightness

    def set_covering_state(self, brightness, onOffStatevalue):
        if self.plugin.debug6:
            logger.debug("Window: set Window state called with values {}, onOffState {}, and inverse {}".format(brightness, onOffStatevalue, self._inverse))
        if brightness is not None:
            if self._inverse == False:
                self.char_target_position.set_value(brightness)
                self.char_current_position.set_value(brightness)
            else:
                brightness =  100 - brightness
                self.char_target_position.set_value(brightness)
                self.char_current_position.set_value(brightness)
        else:  ## onOffState
            if onOffStatevalue is not None:
                if self._inverse == False:
                    if onOffStatevalue:
                        self.char_target_position.set_value(100)
                        self.char_current_position.set_value(100)
                    else:
                        self.char_target_position.set_value(0)
                        self.char_current_position.set_value(0)
                else:
                    if onOffStatevalue:
                        self.char_target_position.set_value(0)
                        self.char_current_position.set_value(0)
                    else:
                        self.char_target_position.set_value(100)
                        self.char_current_position.set_value(100)

    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Window: _set_Chars received : {char_values}")

        if isinstance(char_values,dict):
            if "TargetPosition" in char_values:
                if self.plugin.debug6:
                    logger.debug('TargetPosition wished to be {}, converted to and sending to Indigo'.format( char_values))
                if self._inverse == False:
                    if int(char_values['TargetPosition']) == 0:
                        char_values["On"] = 0
                    elif int(char_values["TargetPosition"]) == 100:
                        char_values['On'] = 1
                    char_values["Brightness"] = char_values.pop("TargetPosition")  ## replace targetdoorstate with On and send through onOffRelay actioning..
                    if self.plugin.debug6:
                        logger.debug("Char Values converted from TargetPosition to Brightness.  New char_values : {}".format(char_values))
                else:
                    if int(char_values['TargetPosition']) == 100:
                        char_values["On"] = 0
                    elif int(char_values["TargetPosition"]) == 0:
                        char_values['On'] = 1
                    char_values["Brightness"] = char_values.pop("TargetPosition")
                    char_values["Brightness"] = int(100 - char_values["Brightness"])
                    ## replace targetdoorstate with On and send through onOffRelay actioning..
                    if self.plugin.debug6:
                        logger.debug("Inverse: Char Values converted from TargetPosition to Brightness.  New char_values : {}".format(char_values))

                self.plugin.Plugin_setter_callback(self, "onOffState", char_values)

class MotionSensor(Accessory):

    category = CATEGORY_SENSOR

    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):#self, *args, **kwargs):
        super().__init__( driver, plugin, indigodeviceid, display_name, aid)# *args, **kwargs)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid

        ## Add below for all Sensor Device Types
        self._char_battery = None
        self._char_charging = None
        self._char_low_battery = None

        batteryLevel = None
        # add battery service to each Sensor - prelim below
        indigodevice = indigo.devices[indigodeviceid]
        batterySupported = indigodevice.ownerProps.get("SupportsBatteryLevel", False)
        if batterySupported:
            if "batteryLevel" in indigodevice.states:
                batteryLevel = HKutils.convert_to_float(indigodevice.states["batteryLevel"])

        serv_temp = self.add_preload_service('MotionSensor')

        if batteryLevel:
            serv_battery = self.add_preload_service("BatteryService")
            self._char_battery = serv_battery.configure_char(CHAR_BATTERY_LEVEL, value=batteryLevel)
            self._char_charging = serv_battery.configure_char(
                "ChargingState", value=2            )
            self._char_low_battery = serv_battery.configure_char(
                "StatusLowBattery", value=0            )

        self.char_on = serv_temp.configure_char( 'MotionDetected', value=False) # set to false at startupgetter_callback=self.get_bulb)
        serv_temp.setter_callback = self._set_chars

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    # def set_bulb(self, value):
    #     if self.plugin.debug6:
    #         logger.debug("Bulb value: {}".format( value))
    #     self.plugin.Plugin_setter_callback(self, "onOffState", value)

    # def get_bulb(self):
    #     value = self.plugin.Plugin_getter_callback(self, "onOffState")
    #     return value

## Below is new logic - send list of variables changes and let indigo plugin thread manage
## This is for HK-->Indigo changes, other way around...
    def _set_chars(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"{char_values}")

        if "On" in char_values:
            if self.plugin.debug6:
                logger.debug('On changed to: {}, sending to Indigo'.format( char_values["On"]))
            self.plugin.Plugin_setter_callback(self, "onOffState", char_values)  ## probably shoudl check ?senmd
            ## ignore brightness
        if "Brightness" in char_values:
            if self.plugin.debug6:
                logger.debug('Brightness changed to: {} '.format( char_values["Brightness"]))
            self.plugin.Plugin_setter_callback(self, "Brightness", char_values)





### End Home Kit Demos
### Should move to import..