## HomeKit Devices

import logging
from HomeKitDevices import HomeAccessory
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
logger.setLevel(logging.DEBUG)

from HKConstants import *
import HKutils

TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"
TEMP_KELVIN = "K"
DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
UNIT_TO_HOMEKIT = {TEMP_CELSIUS: 0, TEMP_FAHRENHEIT: 1}


class Thermostat(HomeAccessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_THERMOSTAT
    '''
    "Thermostat": {
        "OptionalCharacteristics": [
            "CurrentRelativeHumidity",
            "TargetRelativeHumidity",
            "CoolingThresholdTemperature",
            "HeatingThresholdTemperature",
            "Name"
        ],
        "RequiredCharacteristics": [
            "CurrentHeatingCoolingState",
            "TargetHeatingCoolingState",
            "CurrentTemperature",
            "TargetTemperature",
            "TemperatureDisplayUnits"
        ],
        "UUID": "0000004A-0000-1000-8000-0026BB765291"
    },
       "CurrentHeatingCoolingState": {
      "Format": "uint8",
      "Permissions": [
         "pr",
         "ev"
      ],
      "UUID": "0000000F-0000-1000-8000-0026BB765291",
      "ValidValues": {
         "Cool": 2,
         "Heat": 1,
         "Off": 0
      }
   },
       "TemperatureDisplayUnits": {
      "Format": "uint8",
      "Permissions": [
         "pr",
         "pw",
         "ev"
      ],
      "UUID": "00000036-0000-1000-8000-0026BB765291",
      "ValidValues": {
         "Celsius": 0,
         "Fahrenheit": 1
      }
   },
    '''
    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        try:
            super().__init__( driver, plugin, indigodeviceid, display_name, aid)
            self.plugin = plugin
            self.indigodeviceid = indigodeviceid
            self.chars = ['CurrentHeatingCoolingState',"TargetHeatingCoolingState","CurrentTemperature", "TargetTemperature" ]

            indigodevice = indigo.devices[indigodeviceid]
            ## Heat-only (e.g. floor heating): Off and Heat only, no Auto range, so Siri just changes the target
            self.heat_only = bool(indigodevice.pluginProps.get("HomeKit_heatOnly", False))

            ## get temperature unit we are using
            tempSelector = indigodevice.pluginProps.get("HomeKit_tempSelector", False)  ## True if F
            if tempSelector:
                logger.debug("{} Unit Selected".format(TEMP_FAHRENHEIT))
                self._unit = TEMP_FAHRENHEIT
            else:
                logger.debug("{} unit Selected".format(TEMP_CELSIUS))
                self._unit = TEMP_CELSIUS

            # hc_min_temp = 20.0  ## defaultss
            # hc_max_temp = 24.0
            # setpointCool = DEFAULT_MIN_TEMP
            # setpointHeat = DEFAULT_MAX_TEMP
            hc_min_temp = DEFAULT_MIN_TEMP
            hc_max_temp = DEFAULT_MAX_TEMP

       #      if "setpointCool" in indigodevice.states:
       #           setpointCool = float(indigodevice.states["setpointCool"])
       #      if "setpointHeat" in indigodevice.states:
       #           setpointHeat = float(indigodevice.states["setpointHeat"])
       #      logger.DEBUG("Set SetPoints.")
       #    #  def _get_temperature_range_from_state(unit, setpointCool, setpointHeat, default_min, default_max):
       #
       # #      Below incorrect min and max - hardware min and max - not setpoints that I'm pulling
            # in absence of this data from indigo - use defaults

        #    hc_min_temp,hc_max_temp = _get_temperature_range_from_state(self._unit, setpointCool, setpointHeat, DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP )
            logger.debug("Found Min {} and Max {} Temperatures ".format(hc_min_temp,hc_max_temp))
            ## also seems Indigo has heat and cool min/max
            ## get indigo device info and set within each Accessory whether F or C, then convert everything.. and set DisplayUnits

            if not self.heat_only:
                self.chars.extend(    ( CHAR_COOLING_THRESHOLD_TEMPERATURE, CHAR_HEATING_THRESHOLD_TEMPERATURE)      )
            logger.debug("Thermostat Device using Chars: {}".format(self.chars))
            serv_thermostat = self.add_preload_service('Thermostat', self.chars)

            if self.heat_only:
                self.char_current_heat_cool = serv_thermostat.configure_char( 'CurrentHeatingCoolingState', value= 0, valid_values={"Off": 0, "Heat": 1}, getter_callback=self.get_currentState )
                self.char_target_heat_cool = serv_thermostat.configure_char( "TargetHeatingCoolingState", value= 0, valid_values={"Off": 0, "Heat": 1}, getter_callback = self.get_targetState )
                self.char_target_heat_cool.allow_invalid_client_values = True   ## Siri sends Auto anyway: the plugin treats it as Heat (as HA does)
            else:
                self.char_current_heat_cool = serv_thermostat.configure_char( 'CurrentHeatingCoolingState', value= 0, getter_callback=self.get_currentState )
                self.char_target_heat_cool = serv_thermostat.configure_char( "TargetHeatingCoolingState", value= 0, getter_callback = self.get_targetState )
            self.char_current_temp = serv_thermostat.configure_char("CurrentTemperature", getter_callback=self.get_temp )

            '''
               "TargetTemperature": {
                  "Format": "float",
                  "Permissions": [
                     "pr",
                     "pw",
                     "ev"
                  ],
                  "UUID": "00000035-0000-1000-8000-0026BB765291",
                  "maxValue": 38,
                  "minStep": 0.1,
                  "minValue": 10,
                  "unit": "celsius"
               },
            '''

            ## OKAY update
            ## TargetTemperature has to be in celsius
            ## CurrentTemperature doesn't care....
            ## HeatingThresholdTemperature Celsuis and limit to 25
            ## CoolingThresholdTemperature the same...
            ## a single system wide F change isn't going to work
            ## needs to be device by device.


            self.char_target_temp = serv_thermostat.configure_char(
                "TargetTemperature",
                value=21.0,
                # We do not set PROP_MIN_STEP here and instead use the HomeKit
                # default of 0.1 in order to have enough precision to convert
                # temperature units and avoid setting to 73F will result in 74F
                properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
                getter_callback=self.get_target_temp
            )
            # Display units characteristic
            if self._unit and self._unit in UNIT_TO_HOMEKIT:
                unit = UNIT_TO_HOMEKIT[self._unit]
                #self.char_display_units.set_value(unit)
            self.char_display_units = serv_thermostat.configure_char(
                "TemperatureDisplayUnits", value=unit
            )


            '''
            "HeatingThresholdTemperature": {
              "Format": "float",
              "Permissions": [
                 "pr",
                 "pw",
                 "ev"
              ],
              "UUID": "00000012-0000-1000-8000-0026BB765291",
              "maxValue": 25,
              "minStep": 0.1,
              "minValue": 0,
              "unit": "celsius"
           },
            '''


            if CHAR_COOLING_THRESHOLD_TEMPERATURE in self.chars:
                self.char_cooling_thresh_temp = serv_thermostat.configure_char(
                    CHAR_COOLING_THRESHOLD_TEMPERATURE,
                    value=23.0,
                    # We do not set PROP_MIN_STEP here and instead use the HomeKit
                    # default of 0.1 in order to have enough precision to convert
                    # temperature units and avoid setting to 73F will result in 74F
                    properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
                    getter_callback = self.get_cool_thresh_temp
                )
            if CHAR_HEATING_THRESHOLD_TEMPERATURE in self.chars:
                self.char_heating_thresh_temp = serv_thermostat.configure_char(
                    CHAR_HEATING_THRESHOLD_TEMPERATURE,
                    value=19.0,
                    # We do not set PROP_MIN_STEP here and instead use the HomeKit
                    # default of 0.1 in order to have enough precision to convert
                    # temperature units and avoid setting to 73F will result in 74F
                    properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
                    getter_callback = self.get_heat_thresh_temp
                )

            # As best as I can see Thermostat Device in Indigo doesn't really do fan speed
            # Disable this for the time being.

            serv_thermostat.setter_callback = self._set_chars  ## Setter for everything
        except:
            logger.exception("error in thermostat device")

    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    def _temperature_to_homekit(self, temp):
        return HKutils.temperature_to_homekit(temp, self._unit)

    def set_temperature(self, temperature, type):
        if self.plugin.debug6:
            logger.debug("set_temp called by Indigo, temperature {} and type {} and units {}".format(temperature,type,self._unit))
        if type == "current":
            self.char_current_temp.set_value(self._temperature_to_homekit(temperature))
        elif type == "target":
            self.char_target_temp.set_value(self._temperature_to_homekit(temperature))
        elif self.heat_only:   ## no Auto range: the heat setpoint is the target
            if type in ("heatthresh", "setpointHeat"):
                self.char_target_temp.set_value(self._temperature_to_homekit(temperature))
        elif type == "coolthresh":
            self.char_cooling_thresh_temp.set_value(self._temperature_to_homekit(temperature))
        elif type == "heatthresh":
            self.char_heating_thresh_temp.set_value(self._temperature_to_homekit(temperature))
        elif type in ("setpointCool", "setpointHeat"):
            hc_hvac_mode = self.char_target_heat_cool.value
            if (hc_hvac_mode == 1 and type == "setpointHeat") or (hc_hvac_mode == 2 and type == "setpointCool"):  ## HEAT  or ## Cool
                self.char_target_temp.set_value(self._temperature_to_homekit(temperature))
            elif hc_hvac_mode == 3: ## AUTO
                if type =="setpointCool":
                    self.char_cooling_thresh_temp.set_value(self._temperature_to_homekit(temperature))
                elif type == "setpointHeat":
                    self.char_heating_thresh_temp.set_value(self._temperature_to_homekit(temperature))

    def update_all_temperatures(self):
        logger.debug("update_all_temperatures called by plugin")
        indigodevice = indigo.devices[self.indigodeviceid]

    def _set_fan_active(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Active: {char_values}")

    def _set_fan_mode(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Mode Auto or Not: {char_values}")


    def _set_fan_speed(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Speed: {char_values}")

    def _set_fan(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.info(f"{char_values}")

    def get_temp(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_temp")
            if self.plugin.debug6:
                logger.debug("Current Temp State:{}".format(value))
            if isinstance(value, (int,float)):
                return self._temperature_to_homekit(value)
            return 0

        except:
            logger.exception("Exception in get temp")

    def get_target_temp(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_target_temp")
            if self.plugin.debug6:
                logger.debug("Current Target Temp State:{}".format(value))
            if isinstance(value, (int,float)):
                return self._temperature_to_homekit(value)
            return 0
        except:
            logger.exception("Exception in get target temp")


    def get_cool_thresh_temp(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_coolthresh_temp")
            if self.plugin.debug6:
                logger.debug("Current Cool Thresh Temp State:{}".format(value))
                logger.debug(f"{value}")
            if isinstance(value, (int,float)):
                return self._temperature_to_homekit(value)
            return 23

            #
        except:
            logger.exception("Exception in get cool thresh temp")

    def get_heat_thresh_temp(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_heatthresh_temp")
            if self.plugin.debug6:
                logger.debug("Current Heat Thresh Temp State:{}".format(value))
            if isinstance(value, (int,float)):
                return self._temperature_to_homekit(value)
            return 19
            #
        except:
            logger.exception("Exception in get heat thresh temp")


    def get_currentState(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_currentState")
            if self.plugin.debug6:
                logger.debug("Current State:{}".format(value))
            if self.heat_only and value not in (0, 1):
                return 0   ## heat-only: cooling shows as idle
            return value
        except:
            logger.exception("get currentState exception")

    def get_targetState(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_targetState")
            #if self.plugin.debug6:
            if self.plugin.debug6:
                logger.debug("Target State:{}".format(value))
            if self.heat_only and value:
                return 1   ## heat-only: Auto or Cool show as Heat
            return value
        except:
            logger.exception("get target state exception")

    async def run(self):
        try:
            if self.plugin.debug6:
                logger.debug("Run called once, add callback to plugin")
            self.plugin.Plugin_addCallbacktoDeviceList(self)
        except:
            logger.exception("Run exception caught")

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
        try:
            if self.plugin.debug6:
                logger.debug(f"{char_values}")
            self.plugin.Plugin_setter_callback(self, "Thermostat_state", char_values)
        except:
            logger.exception("_set chars caught exception")

    ## Thanks HA!

class HeaterCooler(HomeAccessory):
    """An Indigo thermostat as HomeKit's Heater-Cooler (the Home app's air conditioner tile):
    a power button separate from the mode (Heat / Cool / Auto), heat and cool targets.

    A zone (published with 'Zone of' set to its main unit, e.g. an Actron Que zone) only
    switches itself on and off and sets its own targets: it shows the main unit's mode and
    never changes the main unit. The plugin does the Indigo side (Plugin.heater_cooler_*)."""

    category = CATEGORY_AIR_CONDITIONER

    def __init__(self, driver, plugin, indigodeviceid, display_name, aid, values=None, limits=None):
        super().__init__(driver, plugin, indigodeviceid, display_name, aid)
        self.plugin = plugin
        self.indigodeviceid = indigodeviceid
        values = {k: v for k, v in (values or {}).items() if v is not None}   ## None = unknown: use the defaults below
        limits = limits or {}
        ## Only what the Indigo thermostat supports: a cooling-only AC gets Cool only, no heat target
        heat, cool = limits.get("heat", True), limits.get("cool", True)
        if not heat and not cool:
            heat = cool = True
        modes = {}
        if heat and cool:
            modes["Auto"] = 0
        if heat:
            modes["Heat"] = 1
        if cool:
            modes["Cool"] = 2
        self.modes = set(modes.values())
        optional = ['TemperatureDisplayUnits']
        if cool:
            optional.append(CHAR_COOLING_THRESHOLD_TEMPERATURE)
        if heat:
            optional.append(CHAR_HEATING_THRESHOLD_TEMPERATURE)
        serv = self.add_preload_service('HeaterCooler', optional)
        target = values.get("TargetHeaterCoolerState", 2 if cool else 1)
        if target not in self.modes:
            target = 2 if cool else 1
        self.chars = {
            "Active": serv.configure_char("Active", value=values.get("Active", 0)),
            "CurrentHeaterCoolerState": serv.configure_char("CurrentHeaterCoolerState", value=values.get("CurrentHeaterCoolerState", 0)),
            "TargetHeaterCoolerState": serv.configure_char("TargetHeaterCoolerState", valid_values=modes),
            "CurrentTemperature": serv.configure_char("CurrentTemperature", value=values.get("CurrentTemperature", 0)),
        }
        self.chars["TargetHeaterCoolerState"].set_value(target, should_notify=False)
        if cool:
            self.chars[CHAR_COOLING_THRESHOLD_TEMPERATURE] = serv.configure_char(
                CHAR_COOLING_THRESHOLD_TEMPERATURE, value=values.get(CHAR_COOLING_THRESHOLD_TEMPERATURE, 24),
                properties={PROP_MIN_VALUE: limits.get("cool_min", 10), PROP_MAX_VALUE: limits.get("cool_max", 35)})
        if heat:
            self.chars[CHAR_HEATING_THRESHOLD_TEMPERATURE] = serv.configure_char(
                CHAR_HEATING_THRESHOLD_TEMPERATURE, value=values.get(CHAR_HEATING_THRESHOLD_TEMPERATURE, 20),
                properties={PROP_MIN_VALUE: limits.get("heat_min", 0), PROP_MAX_VALUE: limits.get("heat_max", 30)})
        serv.configure_char("TemperatureDisplayUnits", value=limits.get("display_units", 0))
        serv.setter_callback = self._set_chars

    async def run(self):
        if self.plugin.debug6:
            logger.debug("Heater-Cooler Run called once, add callback to plugin")
        self.plugin.Plugin_addCallbacktoDeviceList(self)

    def _set_chars(self, char_values):
        if self.plugin.debug6:
            logger.debug(f"Heater-Cooler set: {char_values}")
        self.plugin.heater_cooler_set(self, char_values)

    def update(self, values):
        """New values from Indigo (only changed ones are sent to HomeKit)."""
        for name, value in values.items():
            char = self.chars.get(name)
            if name == "TargetHeaterCoolerState" and value not in self.modes:
                continue   ## e.g. Auto on a cooling-only unit: keep showing the last valid mode
            if char is not None and value is not None and char.value != value:
                char.set_value(value)


class ThermostatZone(HomeAccessory):
    ## get has no value otherwise HomeKit crashes with no errors or at least that is what I am hoping will fix this particularly annoying error...

    category = CATEGORY_THERMOSTAT
    '''
    "Thermostat": {
        "OptionalCharacteristics": [
            "CurrentRelativeHumidity",
            "TargetRelativeHumidity",
            "CoolingThresholdTemperature",
            "HeatingThresholdTemperature",
            "Name"
        ],
        "RequiredCharacteristics": [
            "CurrentHeatingCoolingState",
            "TargetHeatingCoolingState",
            "CurrentTemperature",
            "TargetTemperature",
            "TemperatureDisplayUnits"
        ],
        "UUID": "0000004A-0000-1000-8000-0026BB765291"
    },
       "CurrentHeatingCoolingState": {
      "Format": "uint8",
      "Permissions": [
         "pr",
         "ev"
      ],
      "UUID": "0000000F-0000-1000-8000-0026BB765291",
      "ValidValues": {
         "Cool": 2,
         "Heat": 1,
         "Off": 0
      }
   },
       "TemperatureDisplayUnits": {
      "Format": "uint8",
      "Permissions": [
         "pr",
         "pw",
         "ev"
      ],
      "UUID": "00000036-0000-1000-8000-0026BB765291",
      "ValidValues": {
         "Celsius": 0,
         "Fahrenheit": 1
      }
   },
    '''
    def __init__(self, driver, plugin, indigodeviceid,  display_name, aid):
        try:
            super().__init__( driver, plugin, indigodeviceid, display_name, aid)
            self.plugin = plugin
            self.indigodeviceid = indigodeviceid
            self.chars = ['CurrentHeatingCoolingState',"TargetHeatingCoolingState","CurrentTemperature", "TargetTemperature" ]

            indigodevice = indigo.devices[indigodeviceid]

            ## get temperature unit we are using
            tempSelector = indigodevice.pluginProps.get("HomeKit_tempSelector", False)  ## True if F
            if tempSelector:
                logger.debug("{} Unit Selected".format(TEMP_FAHRENHEIT))
                self._unit = TEMP_FAHRENHEIT
            else:
                logger.debug("{} unit Selected".format(TEMP_CELSIUS))
                self._unit = TEMP_CELSIUS

            # hc_min_temp = 20.0  ## defaultss
            # hc_max_temp = 24.0
            # setpointCool = DEFAULT_MIN_TEMP
            # setpointHeat = DEFAULT_MAX_TEMP
            hc_min_temp = DEFAULT_MIN_TEMP
            hc_max_temp = DEFAULT_MAX_TEMP

            logger.debug("Found Min {} and Max {} Temperatures ".format(hc_min_temp,hc_max_temp))
            ## also seems Indigo has heat and cool min/max
            ## get indigo device info and set within each Accessory whether F or C, then convert everything.. and set DisplayUnits

            self.chars.extend(    ( CHAR_COOLING_THRESHOLD_TEMPERATURE, CHAR_HEATING_THRESHOLD_TEMPERATURE)      )
            logger.debug("Thermostat Device using Chars: {}".format(self.chars))
            serv_thermostat = self.add_preload_service('Thermostat', self.chars)

            self.char_current_heat_cool = serv_thermostat.configure_char( 'CurrentHeatingCoolingState', value= 0, getter_callback=self.get_currentState )
            self.char_target_heat_cool = serv_thermostat.configure_char( "TargetHeatingCoolingState", value= 0, getter_callback = self.get_targetState )
            self.char_current_temp = serv_thermostat.configure_char("CurrentTemperature", getter_callback=self.get_temp )

            '''
               "TargetTemperature": {
                  "Format": "float",
                  "Permissions": [
                     "pr",
                     "pw",
                     "ev"
                  ],
                  "UUID": "00000035-0000-1000-8000-0026BB765291",
                  "maxValue": 38,
                  "minStep": 0.1,
                  "minValue": 10,
                  "unit": "celsius"
               },
            '''

            ## OKAY update
            ## TargetTemperature has to be in celsius
            ## CurrentTemperature doesn't care....
            ## HeatingThresholdTemperature Celsuis and limit to 25
            ## CoolingThresholdTemperature the same...
            ## a single system wide F change isn't going to work
            ## needs to be device by device.


            self.char_target_temp = serv_thermostat.configure_char(
                "TargetTemperature",
                value=21.0,
                # We do not set PROP_MIN_STEP here and instead use the HomeKit
                # default of 0.1 in order to have enough precision to convert
                # temperature units and avoid setting to 73F will result in 74F
                properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
            )
            # Display units characteristic
            if self._unit and self._unit in UNIT_TO_HOMEKIT:
                unit = UNIT_TO_HOMEKIT[self._unit]
                #self.char_display_units.set_value(unit)
            self.char_display_units = serv_thermostat.configure_char(
                "TemperatureDisplayUnits", value=unit
            )


            '''
            "HeatingThresholdTemperature": {
              "Format": "float",
              "Permissions": [
                 "pr",
                 "pw",
                 "ev"
              ],
              "UUID": "00000012-0000-1000-8000-0026BB765291",
              "maxValue": 25,
              "minStep": 0.1,
              "minValue": 0,
              "unit": "celsius"
           },
            '''


            if CHAR_COOLING_THRESHOLD_TEMPERATURE in self.chars:
                self.char_cooling_thresh_temp = serv_thermostat.configure_char(
                    CHAR_COOLING_THRESHOLD_TEMPERATURE,
                    value=23.0,
                    # We do not set PROP_MIN_STEP here and instead use the HomeKit
                    # default of 0.1 in order to have enough precision to convert
                    # temperature units and avoid setting to 73F will result in 74F
                    properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
                )
            if CHAR_HEATING_THRESHOLD_TEMPERATURE in self.chars:
                self.char_heating_thresh_temp = serv_thermostat.configure_char(
                    CHAR_HEATING_THRESHOLD_TEMPERATURE,
                    value=19.0,
                    # We do not set PROP_MIN_STEP here and instead use the HomeKit
                    # default of 0.1 in order to have enough precision to convert
                    # temperature units and avoid setting to 73F will result in 74F
                    properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
                )

            # As best as I can see Thermostat Device in Indigo doesn't really do fan speed
            # Disable this for the time being.

            serv_thermostat.setter_callback = self._set_chars  ## Setter for everything

        except:
            logger.exception("error in thermostat device")

    ## The below runs once on creation of bridge/accessory to return the hook back to this accessory object
    ##
    def _temperature_to_homekit(self, temp):
        return HKutils.temperature_to_homekit(temp, self._unit)

    def set_temperature(self, temperature, type):
        #logger.debug("set_temp called by Indigo, temperature {} and type {} and units {}".format(temperature,type,self._unit))
        if type == "current":
            self.char_current_temp.set_value(self._temperature_to_homekit(temperature))
        # if type == "setpointCool":
        #     self.char_current_temp.set_value(self._temperature_to_homekit(temperature))

    def _set_fan_active(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Active: {char_values}")

    def _set_fan_mode(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Mode Auto or Not: {char_values}")


    def _set_fan_speed(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.debug(f"Set Fan Speed: {char_values}")

    def _set_fan(self, char_values):
        """This will be called every time the value of one of the
        characteristics on the service changes.
        """
        if self.plugin.debug6:
            logger.info(f"{char_values}")

    def get_temp(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_temp")

            if self.plugin.debug6:
                logger.debug("Current Temp State:{}".format(value))
            if value == None:
                value = 0
            return self._temperature_to_homekit(value)
           # return value
        except:
            logger.exception("Exception in get temp")

    def get_currentState(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_currentState")
            if self.plugin.debug6:
                logger.debug("Current State:{}".format(value))
            return value
        except:
            logger.exception("get currentState exception")

    def get_targetState(self):
        try:
            value = self.plugin.Plugin_getter_callback(self, "Thermostat_targetState")
            #if self.plugin.debug6:
            if self.plugin.debug6:
                logger.debug("Target State:{}".format(value))
            return value
        except:
            logger.exception("get target state exception")

    async def run(self):
        try:
            if self.plugin.debug6:
                logger.debug("Run called once, add callback to plugin")
            self.plugin.Plugin_addCallbacktoDeviceList(self)
        except:
            logger.exception("Run exception caught")

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
        try:
            if self.plugin.debug6:
                logger.debug(f"{char_values}")
            self.plugin.Plugin_setter_callback(self, "Thermostat_state", char_values)
        except:
            logger.exception("_set chars caught exception")

    ## Thanks HA!

def _get_temperature_range_from_state(unit, setpointCool, setpointHeat, default_min, default_max):
    """Calculate the temperature range from a state."""
    if min_temp := setpointCool:
        min_temp = round(HKutils.temperature_to_homekit(min_temp, unit) * 2) / 2
    else:
        min_temp = default_min
    if max_temp := setpointHeat:
        max_temp = round(HKutils.temperature_to_homekit(max_temp, unit) * 2) / 2
    else:
        max_temp = default_max
    # Homekit only supports 10-38, overwriting
    # the max to appears to work, but less than 0 causes
    # a crash on the home app
    min_temp = max(min_temp, 0)
    if min_temp > max_temp:
        max_temp = min_temp
    return min_temp, max_temp
