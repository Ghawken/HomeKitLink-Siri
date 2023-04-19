#! /usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Author: GlennNZ

"""
import asyncio
import threading
import subprocess
import traceback
import webbrowser


from queue import Queue

import logging
from logging.handlers import TimedRotatingFileHandler

try:
    import requests
except:
    pass

import time as t

import sys
import os
from os import path

import colorsys
import logging

# import applescript
import xml.dom.minidom
import random
import shutil
from os import listdir
from os.path import isfile, join

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.iid_manager import HomeIIDManager, AccessoryIIDStorage

from zeroconf.asyncio import AsyncZeroconf, IPVersion, Zeroconf, InterfaceChoice

from packaging import version

try:
    import indigo
except:
    pass

try:
    import pydevd_pycharm
    pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
except:
    pass

from HomeKitDevices import HomeAccessory, HomeDriver, HomeBridge

import HKSecuritySystem
import HomeKitDevices
import HKConstants
import HKDevicesCamera
import HKDevicesCameraSecuritySpy
import HKThermostat
import HKutils

MAX_NAME_LENGTH = 64
MAX_SERIAL_LENGTH = 64
MAX_MODEL_LENGTH = 64
MAX_VERSION_LENGTH = 64
MAX_MANUFACTURER_LENGTH = 64

################################################################################
# New Indigo Log Handler - display more useful info when debug logging
# update to python3 changes
################################################################################
class IndigoLogHandler(logging.Handler):
    def __init__(self, display_name, level=logging.NOTSET):
        super().__init__(level)
        self.displayName = display_name

    def emit(self, record):
        """ not used by this class; must be called independently by indigo """
        logmessage = ""
        try:
            levelno = int(record.levelno)
            is_error = False
            is_exception = False
            if self.level <= levelno:  ## should display this..
                if record.exc_info !=None:
                    is_exception = True
                if levelno == 5:	# 5
                    logmessage = '({}:{}:{}): {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                elif levelno == logging.DEBUG:	# 10
                    logmessage = '({}:{}:{}): {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                elif levelno == logging.INFO:		# 20
                    logmessage = record.getMessage()
                elif levelno == logging.WARNING:	# 30
                    logmessage = record.getMessage()
                elif levelno == logging.ERROR:		# 40
                    logmessage = '({}: Function: {}  line: {}):    Error :  Message : {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                    is_error = True
                if is_exception:
                    logmessage = '({}: Function: {}  line: {}):    Exception :  Message : {}'.format(path.basename(record.pathname), record.funcName, record.lineno, record.getMessage())
                    indigo.server.log(message=logmessage, type=self.displayName, isError=is_error, level=levelno)
                    if record.exc_info !=None:
                        etype,value,tb = record.exc_info
                        tb_string = "".join(traceback.format_tb(tb))
                        indigo.server.log(f"Traceback:\n{tb_string}", type=self.displayName, isError=is_error, level=levelno)
                        indigo.server.log(f"Error in plugin execution:\n\n{traceback.format_exc(30)}", type=self.displayName, isError=is_error, level=levelno)
                    indigo.server.log(f"\nExc_info: {record.exc_info} \nExc_Text: {record.exc_text} \nStack_info: {record.stack_info}",type=self.displayName, isError=is_error, level=levelno)
                    return
                indigo.server.log(message=logmessage, type=self.displayName, isError=is_error, level=levelno)
        except Exception as ex:
            indigo.server.log(f"Error in Logging: {ex}",type=self.displayName, isError=is_error, level=levelno)

################################################################################
# Use uniqueQueue to avoid multiple camera images pending
################################################################################
class UniqueQueue(Queue):
    def put(self, item, block=False, timeout=None):
        if item not in self.queue:  # fix join bug
            Queue.put(self, item, block, timeout)
    def _init(self, maxsize):
        self.queue = set()
    def _put(self, item):
        self.queue.add(item)
    def _get(self):
        return self.queue.pop()
################################################################################
class IndigoZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""
    def close(self) -> None:
        """Fake method to avoid integrations closing it."""
    indigo_close = Zeroconf.close

class IndigoAsyncZeroconf(AsyncZeroconf):
    """Indigo version of AsyncZeroconf."""
    async def async_close(self) -> None:
        """Fake method to avoid bridges closing it."""
    indigo_async_close = AsyncZeroconf.async_close

################################################################################
class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        ################################################################################
        # Setup Logging
        ################################################################################
        self.logger.setLevel(logging.DEBUG)
        try:
            self.logLevel = int(self.pluginPrefs["showDebugLevel"])
            self.fileloglevel = int(self.pluginPrefs["showDebugFileLevel"])
        except:
            self.logLevel = logging.INFO
            self.fileloglevel = logging.DEBUG

        self.logger.removeHandler(self.indigo_log_handler)

        self.indigo_log_handler = IndigoLogHandler(pluginDisplayName, logging.INFO)
        ifmt = logging.Formatter("%(message)s")
        self.indigo_log_handler.setFormatter(ifmt)
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.addHandler(self.indigo_log_handler)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)s\t%(name)s.%(funcName)s:\t%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)
        self.plugin_file_handler.setLevel(self.fileloglevel)

        logging.getLogger("zeroconf").addHandler(self.plugin_file_handler)

        ################################################################################
        # Finish Logging changes
        ################################################################################

        try:
            import cryptography
        except ImportError:
            raise ImportError("\n{0:=^100}\n{1:=^100}\n{2:=^100}\n{3:=^100}\n{4:=^100}\n{5:=^100}\n".format("=", " Fatal Error Starting HomeKitLink-Siri Plugin  ", " Missing required Library; Cryptography missing ", " Run 'pip3 install cryptograph' in a Terminal window ", " and then restart plugin. ", "="))

        self.logger.debug(u"logLevel = " + str(self.logLevel))
        self.reStartBRIDGE = False
        self.portsinUse = set()

        '''
        Okay - naming dataset
        self.device_list = is set of all devices that seemed to be marked for publishing to Homekit.  Every one. From the device pluginprops HomeKit_publish
        self.device_list_internal = is list of dicts - including HomeKit accessory class object reference for all RUNNING devices with Turned on bridges
        Issue here is some bridges disabled etc.. so this list only includes up and going HomeKit accessories
        Finally:
        self_device_list_internal_idonly = should be the same as above, exactly, but only ID numbers.  Faster checking against deviceUpdate match, probably only
        picoseconds - but still..
        Menu item Show internal List published the results of 2 of these to to log.
        '''

        ## below not used
        self.driver = None
        self.bridge = None
        ##
        # Thread if Camera accessories, started elsewhere.
        self.cameraSnapShots = threading.Thread(target=self.thread_cameraSnapShots, daemon=True)
        self.device_list = set()
        self.device_list_internal = []
        self.device_list_internal_idonly = []
        self.pluginStartingUp = True
        self.pluginDisplayName = pluginDisplayName
        self.pluginId = pluginId
        self.pluginVersion = pluginVersion
        self.pluginIndigoVersion = indigo.server.version

        self.pluginPath = os.getcwd()
        self.listofenabledcameras = []
        self.camera_snapShot_Requested_que = UniqueQueue()  # queue.Queue()
        self.count = 0
        self.deviceBridgeNumber = []
        ## Internal list added to at device startup of Devices internal bridge numbering
        ## Saved to device pluginProps
        ## If device deleted -- capture this with deviceupdate and delete all accessory info for this bridge/stop bridge number..
        ## If new device - increment number as long as unique.  Do so in DeviceStart

        self.subTypesSupported = ["HueLightBulb", "Lock", "LightBulb", "MotionSensor", "GarageDoor", "Fan", "TemperatureSensor", "Switch", "Outlet", "OccupancySensor", "ContactSensor", "CarbonDioxideSensor", "BlueIrisCamera"]

        self.homeKitSubTypes = {"service_Switch": [ "Switch", "Fan", "Outlet", "LightBulb", "Valve", "Irrigation", "Faucet", "Showerhead","GarageDoor","Door"],
                                "service_Camera": ["BlueIrisCamera", "SecuritySpyCamera"],
                                "service_LockMechanism": ["Lock"],
                                "service_Fanv2": ["Fan"],
                                "service_Outlet": ["Outlet"],
                                "service_LeakSensor": ["LeakSensor"],
                                "service_LightSensor": ["LightSensor"],
                                "service_SmokeSensor": ["SmokeSensor", "CarbonDioxideSensor", "CarbonMonoxideSensor"],
                                "service_GarageDoorOpener": ["GarageDoor", "Door"],
                                "service_MotionSensor": ["MotionSensor", "ContactSensor", "OccupancySensor"],
                                "service_Thermostat": ["Thermostat"],
                                "service_TemperatureSensor": ["TemperatureSensor"],
                                "service_HumiditySensor": ["HumiditySensor"],
                                "service_Lightbulb": ["LightBulb", "LightBulb_switch"], #, "LightBulb_Adaptive"],
                                "service_WindowCovering" : ["Blind"],
                                "service_Window" : ["Window"],
                                "service_Security" :["Security"]
                                }

        self.driver_multiple = []
        self.bridge_multiple = []
        self.driverthread_multiple = []
        # delete below once refactored TODO
        self.driverthread = None
        self.prefsUpdated = False
        self.logger.info(u"")

        self.plugin_iidstorage = None

        self.logger.info("{0:=^130}".format(" Initializing New Plugin Session "))
        self.logger.info("{0:<30} {1}".format("Plugin name:", pluginDisplayName))
        self.logger.info("{0:<30} {1}".format("Plugin version:", pluginVersion))
        self.logger.info("{0:<30} {1}".format("Plugin ID:", pluginId))
        self.logger.info("{0:<30} {1}".format("Indigo version:", indigo.server.version))
        self.logger.info("{0:<30} {1}".format("Python version:", sys.version.replace('\n', '')))
        self.logger.info("{0:<30} {1}".format("Python Directory:", sys.prefix.replace('\n', '')))
        self.logger.info("")
        self.pluginprefDirectory = '{}/Preferences/Plugins/com.GlennNZ.indigoplugin.HomeKitLink-Siri'.format(indigo.server.getInstallFolderPath())

        # Change to logging

        self.runningAccessoryCount = 0
        self.debug1 = self.pluginPrefs.get('debug1', False)
        self.debug2 = self.pluginPrefs.get('debug2', False)
        self.debug3 = self.pluginPrefs.get('debug3', False)
        self.debug4 = self.pluginPrefs.get('debug4', False)
        self.debug5 = self.pluginPrefs.get('debug5', False)
        self.debug6 = self.pluginPrefs.get('debug6', False)
        self.debug7 = self.pluginPrefs.get('debug7', False)
        self.debug8 = self.pluginPrefs.get('debug8', False)
        self.debug9 = self.pluginPrefs.get('debug9', False)
        self.debug10 = self.pluginPrefs.get('debug10', False)

        logging.getLogger("zeroconf").setLevel(self.fileloglevel)

        self.previousVersion = self.pluginPrefs.get("previousVersion","0.0.1")
        self.low_battery_threshold = int(self.pluginPrefs.get("batterylow",20))

        self.debugDeviceid = -3  ## always set this to not on after restart.

        if self.debug3:
            logging.getLogger("Plugin.HomeKit_pyHap").setLevel(logging.DEBUG)
        else:
            logging.getLogger("Plugin.HomeKit_pyHap").setLevel(logging.INFO)

        if self.debug10:
            logging.getLogger("zeroconf").setLevel(logging.DEBUG)
        else:
            logging.getLogger("zeroconf").setLevel(logging.ERROR)

        self.ffmpeg_lastCommand = []

        self.startingPortNumber = int(self.pluginPrefs.get('basePortnumber', 51826))
        self.logClientConnected = self.pluginPrefs.get("logClientConnected", True)

        ip_version = self.pluginPrefs.get('mDNSipversion', "ALL")
        if ip_version == "ALL":
            self.select_ip_version = IPVersion.All
        elif ip_version == "V4Only":
            self.select_ip_version = IPVersion.V4Only
        elif ip_version == "V6Only":
            self.select_ip_version = IPVersion.V6Only
        else:
            self.select_ip_version = IPVersion.All
            self.logger.warning("Select_IP: Advanced plugin Properties in error, using default, please check plugin Config")

        interfaces = self.pluginPrefs.get('mDNSinterfaces', "")
        if interfaces == "":
            self.select_interfaces = InterfaceChoice.All
        elif "," in interfaces:
            self.select_interfaces = interfaces.split(",")
            self.logger.debug(f"mDNS Interface List to use: {self.select_interfaces}")
        elif "." in interfaces:
            self.select_interfaces = [interfaces]
        else:
            self.select_interfaces = InterfaceChoice.All
            self.logger.warning("Select_Interface: Advanced plugin Properties in error, using default, please check plugin Config")

        self.apple_2p2 = self.pluginPrefs.get('mDNSapple_p2p', False)
        if self.apple_2p2:
            self.logger.info("You have selected the use of Apple Peer to Peer network")
            self.logger.info("This uses apples Apple Wireless Direct Link for communication between this mac and Home Devices ")
            self.logger.info("This is untested and largely included for full support.")
            self.logger.info("I would not recommend it's usage except in very specific circumstances...")

        self.HAPipaddress = self.pluginPrefs.get('HAPipaddress', "")
        if self.HAPipaddress == "":
            self.HAPipaddress = None

        self.logClientConnected = self.pluginPrefs.get("logClientConnected", True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.zc = IndigoZeroconf(ip_version=self.select_ip_version, interfaces=self.select_interfaces,  apple_p2p=self.apple_2p2)

        self.logger.debug(f"\nmDNS Setup: {self.select_interfaces}\n{self.select_ip_version}\n{self.apple_2p2}")

        self.async_zeroconf_instance = IndigoAsyncZeroconf(zc=self.zc)

        self.logger.info(u"{0:=^130}".format(" End Initializing New Plugin  "))

        try:
            if version.parse(pluginVersion) != version.parse(self.previousVersion):
                self.logger.info("HomeKitLink Updated Version Detected.  Please run xattr command as below (copy & paste to terminal)")
                self.logger.info("")
                self.logger.info("{}".format("sudo xattr -rd com.apple.quarantine '" + indigo.server.getInstallFolderPath() + "/" + "Plugins'"))
                self.logger.info(u"{0:=^130}".format(" End of Setup "))
                self.pluginPrefs['previousVersion']= pluginVersion
        except:
            pass



    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.debugLog(u"closedPrefsConfigUi() method called.")
        if self.debug1:
            self.logger.debug(f"valuesDict\n {valuesDict}")
        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")
        if not userCancelled:
            self.logLevel = int(valuesDict.get("showDebugLevel", '5'))
            self.fileloglevel = int(valuesDict.get("showDebugFileLevel", '5'))
            self.debug1 = valuesDict.get('debug1', False)
            self.debug2 = valuesDict.get('debug2', False)
            self.debug3 = valuesDict.get('debug3', False)
            self.debug4 = valuesDict.get('debug4', False)
            self.debug5 = valuesDict.get('debug5', False)
            self.debug6 = valuesDict.get('debug6', False)
            self.debug7 = valuesDict.get('debug7', False)
            self.debug8 = valuesDict.get('debug8', False)
            self.debug9 = valuesDict.get('debug9', False)
            self.debug10 = valuesDict.get('debug10', False)
            self.logClientConnected = valuesDict.get("logClientConnected", True)
            try:
                self.low_battery_threshold = int (valuesDict.get("batterylow",20))
            except ValueError:
                self.low_battery_threshold = 20
                valuesDict['batterylow'] = 20

            try:
                self.debugDeviceid = int(valuesDict.get("debugDeviceid", -3))
            except ValueError:
                self.debugDeviceid = -3

            self.indigo_log_handler.setLevel(self.logLevel)
            self.plugin_file_handler.setLevel(self.fileloglevel)

            if self.debug10:
                logging.getLogger("zeroconf").setLevel(logging.DEBUG)
            else:
                logging.getLogger("zeroconf").setLevel(logging.ERROR)

            if self.debug3:
                logging.getLogger("Plugin.HomeKit_pyHap").setLevel(logging.DEBUG)
            else:
                logging.getLogger("Plugin.HomeKit_pyHap").setLevel(logging.INFO)

            self.logger.debug(u"logLevel = " + str(self.logLevel))
            self.logger.debug(u"User prefs saved.")
            self.logger.debug(u"Debugging on (Level: {0})".format(self.logLevel))
        return True

    # def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
    #     self.logger.debug("closedDeviceConfigUI called")
    #     return True
    # Shut 'em down.

    def dict_to_list(self, dic):  ##
        listdicts = []
        for k, v in dic.items():
            if isinstance(v, dict):
                listdicts.append(v)
        return listdicts

    #    ########################################
    #
    # Indigo Device Startup
    #
    ##############################################
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
    # This routine returns the UI values for the device configuration screen prior to it
    # being shown to the user; it is sometimes used to setup default values at runtime
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
        if self.debug8:
            self.logger.debug(u'Called getDeviceConfigUiValues(self, pluginProps, typeId, devId):')
            self.logger.debug('     ({0}, {1}, {2})'.format(pluginProps, typeId, devId))
        valuesDict = pluginProps
        errorMsgDict = indigo.Dict()

        checkid = pluginProps.get("bridgeUniqueID", "")
        if checkid == "":
            newProps = pluginProps
            deviceidtouse = 0
            try:
                while deviceidtouse == 0:
                    newid = random.randrange(100000, 999999)
                    if int(newid) not in self.deviceBridgeNumber:
                        deviceidtouse = newid
                        break
            except:
                self.logger.exception("Caught in Random Number Generator")
            newProps["bridgeUniqueID"] = int(newid)
            checkid = newid
            pluginProps = newProps

        indigo.devices[int(devId)].updateStateOnServer(key="uniqueID", value=str(checkid))

        return super(Plugin, self).getDeviceConfigUiValues(pluginProps, typeId, devId)

    def deviceStartComm(self, device):
        self.logger.debug(f"{device.name}: Starting {device.deviceTypeId} Device {device.id} ")
        device.stateListOrDisplayStateIdChanged()
        checkid = device.pluginProps.get("bridgeUniqueID", "")
        newProps = device.pluginProps
        self.logger.debug(f"checkid = {checkid} and self.deviceBridgeNumber = {self.deviceBridgeNumber}")

        if checkid == "" or int(checkid) == 99:
            deviceidtouse = 0
            try:
                while deviceidtouse == 0:
                    newid = random.randrange(100000, 999999)  ##update to 9 digits - given busystate saved less likely collusion.
                    if int(newid) not in self.deviceBridgeNumber:
                        deviceidtouse = newid
                        break
            except:
                self.logger.exception("Caught in Random Number Generator")
            newProps["bridgeUniqueID"] = int(newid)
            checkid = newid

        else:
            self.logger.debug("Starting {} HomeKitLink Bridge with Unique Bridge ID {}".format(device.name, checkid))

        if int(checkid) not in self.deviceBridgeNumber:
            self.deviceBridgeNumber.append(int(checkid))

        self.update_deviceList()
        self.create_deviceList_internal()

        device.replacePluginPropsOnServer(newProps)

        device.updateStateOnServer(key="uniqueID", value=str(checkid))
        if device.enabled:
            device.updateStateOnServer(key="Status", value="Starting Up")
            device.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
            self.startsingleBridge(device, uniqueID=checkid)
            # def startsingleBridge(self, device, uniqueID):
        else:
            device.updateStateOnServer(key="Status", value="Disabled")
            device.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

    ########################################
    # Indigo Device Startup
    def deviceStopComm(self, device):
        try:
            self.logger.debug(f"{device.name}: Stopping {device.deviceTypeId} Device {device.id}")
            device.updateStateOnServer(key="Status", value="Off")
            device.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
            # Only one devices === Bridge
            # Need to sort out unique numbering do so at start regardless as no setup needed.
            # Don't run bridge at start?  Actually will have to even if no devices.
            # Probably reasonable.
            # DONE Need QR Code for each Bridge/Device
            checkid = device.pluginProps.get("bridgeUniqueID", "")

            if checkid != "":
                self.logger.debug("Stopping {} HomeKitLink Bridge with Unique Bridge ID {}".format(device.name, checkid))
                if checkid in self.deviceBridgeNumber:
                    self.logger.debug("Checkid {} and total deviceBridgeNumber {}".format(checkid, self.deviceBridgeNumber))
                    self.deviceBridgeNumber.remove(int(checkid))
                    self.logger.debug("After: Checkid {} and total deviceBridgeNumber {}".format(checkid, self.deviceBridgeNumber))
                bridgetobedeleted = None  # = False
                drivertobedeleted = None
                threadtobedeleted = None
                for bridge in self.bridge_multiple:
                    if bridge != None:
                        # self.logger.error(f"Found a Bridge Bridge Id: {bridge.indigodeviceid}")
                        if str(bridge.indigodeviceid) == str(checkid):
                            bridge.stop()
                            bridgetobedeleted = bridge

                if bridgetobedeleted != None:

                    self.bridge_multiple.remove(bridgetobedeleted)
                    self.logger.debug("Removed Bridge {}".format(bridgetobedeleted))

                # I#t appears Accessory Driver handles the below.. which is probably why error dones't exist occasionally
                # Doesnt remove from list
                for driver in self.driver_multiple:
                    if driver != None:
                        if driver.indigodeviceid == str(checkid):
                            drivertobedeleted = driver
                            self.logger.debug(f"Found Driver to stop Driver Id: {driver.indigodeviceid}")
                            try:
                                driver.stop()
                            except RuntimeError:
                                self.logger.debug("Expected when restarting as Daemon threads already closed")
                                pass

                if drivertobedeleted != None:
                    self.portsinUse.discard(drivertobedeleted.state.port)
                    self.logger.debug(f"Driver to be deleted using port {drivertobedeleted.state.port} and portsinUse now {self.portsinUse}")
                    self.driver_multiple.remove(drivertobedeleted)
                    self.logger.debug("Removed Driver {}".format(drivertobedeleted))

                for threads in self.driverthread_multiple:
                    if threads.name == str(checkid):
                        self.logger.debug(f"Found Thread ID to also Stop..{threads.name}")
                        threadtobedeleted = threads
                        threads.join(timeout=5)
                        if threads.is_alive():
                            self.logger.debug("{} Thread is still alive. Timeout occured. Killing.".format(threads.name))
                            self.logger.error("Should restart Plugin ideally as thread not behaving.")
                if threadtobedeleted != None:
                    self.driverthread_multiple.remove(threadtobedeleted)
                    self.logger.debug("Removed Thread object {}".format(threadtobedeleted))

                self.logger.info("{} has completed full Bridge, Driver and Bridge Thread Shutdown.".format(device.name))

        except:
            self.logger.debug("Exception in DeviceStopCom \n", exc_info=True)

    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
        self.logger.debug("ValidateDevice Config UI called {}".format(values_dict))
        return (True, values_dict)

    ########################################
    ########################################
    # Relay / Dimmer Action callback
    ######################
    def actionControlDevice(self, action, dev):
        ###### TURN ON ######
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            # Command hardware module (dev) to turn ON here:
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" on")

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" on failed")

        ###### TURN OFF ######
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            # Command hardware module (dev) to turn OFF here:
            self.logger.debug(f"{dev.name} has PluginProps {dev.pluginProps}")
            # checkid = dev.pluginProps.get("bridgeUniqueID", "")

            dev.updateStateOnServer("onOffState", False)

        #######################################################################
        ###### TOGGLE ######
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            # Command hardware module (dev) to toggle here:
            # ** IMPLEMENT ME **
            new_on_state = not dev.onState
            send_success = True  # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" toggle")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", new_on_state)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" toggle failed")

    def runConcurrentThread(self):
        # Periodically check to see that the subscription hasn't expired and that the reflector is still working.
        try:
            self.sleep(1)
            # move below to individual deviceStart as part of now major refactoring to multiple bridges.
            # self.startBridge()
            if len(self.listofenabledcameras) > 0:
                self.logger.debug("Camera Accessory Found, starting single thread to manage images.")
                self.start_CameraSnapshots()

            self.sleep(5)
            self.pluginStartingUp = False
            self.logger.info('A total of {} devices are currently selected to be published to HomeKit'.format(self.count))
            self.logger.info("{} Home Kit Accessories are now Started.".format(self.runningAccessoryCount))

            if int(self.count) > int(self.runningAccessoryCount):
                self.logger.info('Given this difference, please review devices by Select Menu Item, Show Device Publications for more information.')


            self.sleep(10)

            while True:
                self.sleep(5)

        except self.StopThread:
            ## stop the homekit drivers
            for driver in self.driver_multiple:
                if driver != None:
                    driver.stop()
            for bridge in self.bridge_multiple:
                if bridge != None:
                    bridge.stop()
            for threads in self.driverthread_multiple:
                threads.join(timeout=5)
                if threads.is_alive():
                    self.logger.debug("{} Thread is still alive. Timeout occured. Killing.".format(threads.name))
                    self.logger.info("Restarting Plugin as thread not behaving.")
                    self.restartPlugin()
            self.logger.info("Completing full Bridge Shutdown ...")

        except:
            self.logger.debug("Exception in runConcurrentThread", exc_info=True)
            ## stop the homekit driver
            for driver in self.driver_multiple:
                if driver != None:
                    driver.stop()
            for bridge in self.bridge_multiple:
                if bridge != None:
                    bridge.stop()
            for threads in self.driverthread_multiple:
                threads.join(timeout=5)
                if threads.is_alive():
                    self.logger.debug("{} Thread is still alive. Timeout occured. Killing.".format(threads.name))
                    self.logger.info("Restarting Plugin as thread not behaving.")
                    self.restartPlugin()
            self.logger.info("Completing full Bridge Shutdown ...")

            self.logger.info("Completing full Bridge(s) Shutdown...")
            self.sleep(2)
            ## update all devices and start Bridge again.
            self.driver_multiple = []
            self.bridge_multiple = []
            self.driverthread_multiple = []
            self.update_deviceList()

    def create_deviceList_internal(self):
        self.logger.debug("create Device List Internal called")
        # self.device_list_internal = []

        for item in self.device_list:
            try:
                # self.logger.debug("{}".format(item))
                ## just a list of item numbers all goodies stored in deviceProps
                device = self.return_deviceorAG(item)  # indigo.devices[item]
                if device == None:
                    self.logger.error("Error with this device ID {}.  Skipping.".format(item))
                    continue
                device_props = dict(device.pluginProps)
                devicename = device_props.get("homekit-name", "")
                deviceType = device_props.get("HomeKit_deviceSubtype", "")

                # Move to subtype reflecting plugins belief as to type of Accessory
                # Currently Lightbulb can reflect Lightbulb_switch, HueLightBulb and now ColorTempLightBulb
                # May be others eg. Fan -- I should look at.  Again this subtype reflects the HK Accessory plugin creates
                # Change Subtype to reflect this and then do not check again.
                if str(deviceType) == "LightBulb":
                    supportsRGB = False  ## Defaulting to lamp model
                    supportsWhiteTemperature = False
                    if hasattr(device, "supportsRGB"):
                        supportsRGB = device.supportsRGB
                    if hasattr(device,"supportsWhiteTemperature"):
                        supportsWhiteTemperature = device.supportsWhiteTemperature
                    if supportsRGB and supportsWhiteTemperature:
                        deviceType = "ColorTempLightBulb"  ## Modify the internal list subtype
                    elif supportsRGB and not supportsWhiteTemperature:
                        deviceType = "HueLightBulb"
                    elif "brightnessLevel" in device.states and "brightness" in dir(device):
                        deviceType = "LightBulb"   ## Dimmer variety
                    elif type(device) == indigo.DimmerDevice:
                        deviceType = "LightBulb"  ## Dimmer variety
                    else:
                        ## simple switch
                        deviceType = "LightBulb_switch"
                    if self.debug1:
                        self.logger.debug("LightBulb Device Found and assessed.  Accessory will be a {} type of LightBulb".format(deviceType))
                if str(deviceType) == "Fan":
                    if type(device) == indigo.SpeedControlDevice:
                        deviceType = "Fan"
                    elif "brightnessLevel" in device.states:
                        deviceType = "Fan"
                    else:
                        deviceType = "Fan_switch"
                devicesensor = device_props.get("HomeKit_deviceSensor", "")
                try:
                    deviceBridgeID = int(device_props.get("HomeKit_bridgeUniqueID", 99)  )
                except ValueError:
                    deviceBridgeID = 99
                if type(device) == indigo.ActionGroup:
                    devicemodel = "Action Group"
                    manufacturerName = "Indigo Domotics"
                else:
                    if device.protocol == indigo.kProtocol.ZWave:
                        devicemodel = device.ownerProps.get("zwModelName", "Zwave Model")
                    else:
                        devicemodel = device.model

                    if device.pluginId == "com.perceptiveautomation.indigoplugin.devicecollection":
                        manufacturerName = "Indigo Domotics"
                    elif "manufacturerName" in device.ownerProps:
                        manufacturerName = device.ownerProps["manufacturerName"]
                    elif "manufactureName" in device.ownerProps:
                        manufacturerName = device.ownerProps["manufactureName"]
                    else:
                        if device.protocol == indigo.kProtocol.ZWave:
                            manufacturerName = device.ownerProps.get("zwManufactureName", "Zwave")
                        # elif
                        else:
                            manufacturerName = device.pluginId  ## truncate device name...device.pluginId
                if self.debug1:
                    self.logger.debug("Device: {},  ID: {}  Model: {} Type: {}  Sensor  {}   ManufacturerName: {}".format(devicename, item, devicemodel, deviceType, devicesensor, manufacturerName))
                # self.logger.debug("DeviceBridge Found ={}, and contents of self.deviceBridgeNumber {}".format(deviceBridgeID, self.deviceBridgeNumber))

                ## santise names ## max length of all = 64
                devicename = HKutils.cleanup_name_for_homekit(devicename)
                devicemodel = HKutils.cleanup_name_for_homekit(devicemodel)
                manufacturerName = HKutils.cleanup_name_for_homekit(manufacturerName)

                if deviceBridgeID != 99 and int(deviceBridgeID) in self.deviceBridgeNumber:
                    checkexists = next((i for i, itemtocheck in enumerate(self.device_list_internal) if itemtocheck["deviceid"] == item), None)
                    if checkexists == None:  ## remove those devices that don't have bridge device ID, or arent started
                        ## only add item if doesn't exist
                        self.device_list_internal.append({"deviceid": int(item),
                                                          "devicename": devicename,
                                                          "accessory": None,
                                                          "aid": int(item),
                                                          "subtype": deviceType,
                                                          "bridgeID": int(deviceBridgeID),
                                                          "devicemodel": devicemodel,
                                                          "devicesensor": devicesensor,
                                                          "manufacturername": manufacturerName})
                        self.device_list_internal_idonly.append(int(item))
            except:
                self.logger.exception("Caught Exception with device_list:  Hopefully still adding other devices..")

    # if self.debug1:
    # self.logger.debug("Self Internal List: \n\n:{}".format(self.device_list_internal))

    def get_bridge_multiple(self, driver, bridge, bridgenumber):
        try:
            extend_device_list = []
            self.logger.debug(f"get_bridge_multiple called and self.device_list_internal length {len(self.device_list_internal)}")
            for item in self.device_list_internal:
                if int(item["bridgeID"]) == int(bridgenumber):
                    # self.logger.info("Matching Bridge Found setting up Accessory.")
                    # self.sleep(0.01)
                    self.logger.debug(f"Item :{item} exisits for this bridge {bridge}")
                    indigodevice = self.return_deviceorAG(item["deviceid"])
                    deviceAID = int(str(bridgenumber) + str(item["deviceid"]))
                    if self.debug1:
                        self.logger.debug("Adding Accessory Name: {},  ID  {} , Type: {}".format(item['devicename'], deviceAID, item['subtype']))
                    if item['subtype'] == "LightBulb":
                        accessory = HomeKitDevices.DimmerBulb(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "ColorTempLightBulb":
                        ## this checks inside HueLightBulb for same aspect making colortemp - slightly out of spec
                        accessory = HomeKitDevices.HueLightBulb(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "LightBulb_switch":
                        accessory = HomeKitDevices.LightBulb(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "GarageDoor":
                        accessory = HomeKitDevices.GarageDoor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Door":
                        accessory = HomeKitDevices.DoorDoor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "HueLightBulb":
                        accessory = HomeKitDevices.HueLightBulb(driver, self, item["deviceid"], item['devicename'], aid=int(deviceAID))
                    elif item['subtype'] == "MotionSensor":
                        accessory = HomeKitDevices.MotionSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "TemperatureSensor":
                        accessory = HomeKitDevices.TemperatureSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "LightSensor":
                        accessory = HomeKitDevices.LightSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "HumiditySensor":
                        accessory = HomeKitDevices.HumiditySensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "SmokeSensor":
                        accessory = HomeKitDevices.SmokeSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Switch":
                        accessory = HomeKitDevices.SwitchSimple(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Security":
                        accessory = HKSecuritySystem.SecuritySystem(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Blind":
                        accessory = HomeKitDevices.WindowCovering(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Window":
                        accessory = HomeKitDevices.Window(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Outlet":
                        accessory = HomeKitDevices.Outlet(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "CarbonDioxideSensor":
                        accessory = HomeKitDevices.CarbonDioxideSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "CarbonMonoxideSensor":
                        accessory = HomeKitDevices.CarbonMonoxideSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "ContactSensor":
                        accessory = HomeKitDevices.ContactSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "LeakSensor":
                        accessory = HomeKitDevices.LeakSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "LightSensor":
                        accessory = HomeKitDevices.LightSensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "OccupancySensor":
                        accessory = HomeKitDevices.OccupancySensor(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Lock":
                        accessory = HomeKitDevices.Lock(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Fan":
                        accessory = HomeKitDevices.Fanv2(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Fan_switch":
                        accessory = HomeKitDevices.FanSimple(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Thermostat":
                        accessory = HKThermostat.Thermostat(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "BlueIrisCamera":
                        cameraoptions = self.get_CameraOptions(item["deviceid"])
                        if cameraoptions == None:
                            ## Error
                            self.logger.debug("Error in getting camera settings.  Skipping setup")
                            continue
                        if self.debug7:
                            self.logger.debug("Options:\n\n{}\n".format(cameraoptions))
                        accessory = HKDevicesCamera.Camera(driver, plugin=self, indigodeviceid=item["deviceid"], display_name=item['devicename'], aid=deviceAID, config=cameraoptions)
                        ## start snapshot thread.. to save
                        if "BI_imageURL" in cameraoptions:
                            self.listofenabledcameras.append(cameraoptions)
                        device_add_id = indigodevice.pluginProps.get("HomeKit_doorbellId", "")
                        DoorBelldeviceAID = int(str(bridgenumber) + str(device_add_id))
                        if device_add_id != "":  ## Doorbell ID exists  ## internal list = deviceid = okay to use for accessory but not here..
                            # self.runningAccessoryCount = self.runningAccessoryCount +1
                            extend_device_list.append({"deviceid": int(device_add_id),
                                                       "devicename": "Special-Doorbell",
                                                       "accessory": None,  ##link to accessory
                                                       "aid": int(device_add_id),
                                                       "subtype": "Linked-DoorBell",
                                                       "bridgeID": int(bridgenumber),
                                                       "devicemodel": "Blue Iris DoorBell",
                                                       "devicesensor": "Blue Iris DoorBell",
                                                       "manufacturername": "Blue Iris Linked"
                                                       }
                                                      )
                            self.device_list_internal_idonly.append(int(device_add_id))
                    elif item['subtype'] == "SecuritySpyCamera":
                        cameraoptions = self.get_CameraOptions(item["deviceid"])
                        if cameraoptions == None:
                            ## Error
                            self.logger.debug("Error in getting camera settings.  Skipping setup")
                            continue
                        if self.debug7:
                            self.logger.debug("Options:\n\n{}\n".format(cameraoptions))
                        accessory = HKDevicesCameraSecuritySpy.SecuritySpyCamera(driver, plugin=self, indigodeviceid=item["deviceid"], display_name=item['devicename'], aid=deviceAID, config=cameraoptions)
                        ## start snapshot thread.. to save
                        if "SS_imageURL" in cameraoptions:
                            self.listofenabledcameras.append(cameraoptions)
                        device_add_id = indigodevice.pluginProps.get("HomeKit_doorbellId", "")
                        # self.logger.error("{} type and {} value".format(type(device_add_id),device_add_id))
                        # DoorBelldeviceAID = int("1000" + str(bridgenumber) + str(device_add_id))
                        if device_add_id != "" and str(device_add_id) != "-1":  ## Doorbell ID exists  ## internal list = deviceid = okay to use for accessory but not here..
                            # self.runningAccessoryCount = self.runningAccessoryCount +1
                            extend_device_list.append({"deviceid": int(device_add_id),
                                                       "devicename": "Special-Doorbell",
                                                       "accessory": None,  ##link to accessory
                                                       "aid": int(device_add_id),
                                                       "subtype": "Linked-DoorBell",
                                                       "bridgeID": int(bridgenumber),
                                                       "devicemodel": "Security Spy DoorBell",
                                                       "devicesensor": "Securiy Spy DoorBell",
                                                       "manufacturername": "Securiy Spy Linked"
                                                       }
                                                      )
                            self.device_list_internal_idonly.append(int(device_add_id))
                    elif item['subtype'] == "Valve":
                        accessory = HomeKitDevices.Valve(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Irrigation":
                        accessory = HomeKitDevices.Irrigation(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Showerhead":
                        accessory = HomeKitDevices.Showerhead(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Faucet":
                        accessory = HomeKitDevices.Faucet(driver, self, item["deviceid"], item['devicename'], aid=deviceAID)
                    elif item['subtype'] == "Linked-DoorBell":
                        self.logger.debug("Skipping Linked Doorbell, setup in Camera and does not need own accessory")
                        continue
                    else:
                        self.logger.info("Skipping No Subtype this: ID {}  Name {}  DeviceAID {}".format(item["deviceid"], item['devicename'], deviceAID))
                        continue

                    manufacturer = item['manufacturername']
                    model = item['devicemodel']
                    serial_number = str(deviceAID)
                    firmware_version = str(self.pluginVersion)
                    accessory.set_info_service(manufacturer=manufacturer[:MAX_MANUFACTURER_LENGTH], model=model[:MAX_MODEL_LENGTH], serial_number=serial_number[:MAX_SERIAL_LENGTH], firmware_revision=firmware_version[:MAX_VERSION_LENGTH])
                    self.logger.debug("Adding Accessory:{}".format(accessory))
                    bridge.add_accessory(accessory)

                    # self.runningAccessoryCount = self.runningAccessoryCount +1
                    bridge.set_info_service(firmware_revision=self.pluginVersion, manufacturer="Indigo " + self.pluginIndigoVersion, model="HomeKitLink Bridge " + str(bridgenumber), serial_number=str(bridgenumber) + "1244")
            self.device_list_internal = self.device_list_internal + extend_device_list

            # self.logger.debug("Self.Device_list_internal:\n\n{}\n".format(self.device_list_internal))
            return bridge

        except:
            self.logger.exception("Error in Get Bridge")
        ##

    ###############################################################################
    # Thread to get Cameras
    # Plugin Thread if Cameras enabled only to download from BI and save snapshots
    # Continues via Que as requested by HomeKit.  Does Not run if no cameras enabled.  Does Not Run if no HomeKit screen open
    # Does not hang HomeKit - I note some HomeKit implementations based on Python-HAP library suggest new bridges for each cameras t
    # to overcome hanging...  this fixes that and is better approach in my mind.
    # For the first time with Homekit very happy to enable Cameras because unless app open no impact,  and if open one minimal active thread only for all
    #####################################################################################
    def start_CameraSnapshots(self):
        # self.cameraSnapShots = threading.Thread(target=self.thread_cameraSnapShots, daemon=True)
        # add check for already running, in case of runconcurrent restarting

        # try:
        #     raise TypeError("Testing here")
        # except TypeError as e:
        #     raise Exception("I'm not in a good shape") from e

        if self.cameraSnapShots.is_alive() == False:
            self.logger.info("Camera Thread is being spooled up to manage camera images")
            self.cameraSnapShots.start()

    def thread_cameraSnapShots(self):
        ## with cameras open constantly pulling images and with my example of 21 enabled cameras getting now peeak CPU of about 9-10%
        ## all the time with app open open.  Essentially seems to be downloading images every 10 seconds, across 21 cameras
        ## could drop this back to each camera but still same CPU...
        ## 3 clients open and remains 15 in que... never gets to zero...
        ## need to slow down, time and refresh only when needed.
        ## will need dict of cameras with timestamp and update if >30 seconds or so

        self.logger.debug("Thread for managing all camera snapshots created and started")
        # self.logger.debug("List of enabled Camers = {}".format(self.listofenabledcameras))
        try:
            for camera in self.listofenabledcameras:
                if "BI_name" in camera:
                    CameraName = camera["BI_name"]
                elif "SS_name" in camera:
                    CameraName = camera["SS_name"]
                else:
                    CameraName = ""
                path = self.cameraimagePath + "/" + CameraName + ".jpg"
                # path = self.pluginPath + '/cameras/' + CameraName + '.jpg'
                snapshot_path = self.pluginPath + "/cameras/snapshot.jpg"
                shutil.copy(snapshot_path, path)
                if self.debug7:
                    self.logger.debug("Startup Refresh Snapshots images to Default for Camera: {}".format(path))

            session = requests.Session()
            cameracheck = {}
            while True:
                try:
                    self.sleep(0.05)  ## this made huge difference to CPU... would think would block below..
                    # self.listofenabledcameras
                    (cameraRequested, image_width) = self.camera_snapShot_Requested_que.get(block=True)  ## blocks here
                    ## use tuple for que
                    if self.debug7:
                        self.logger.debug("Got request Image for this camera {} & currently {} items in que".format(cameraRequested, self.camera_snapShot_Requested_que.qsize()))

                    for camera in self.listofenabledcameras:
                        if "BI_name" in camera:
                            # self.logger.info("cameraREquested:{}  and canName:{}".format(cameraRequested, camera["BI_name"]))
                            if camera["BI_name"] == cameraRequested:
                                if self.debug7:
                                    self.logger.debug("Found matching Camera {} = {}".format(camera["BI_name"], cameraRequested))

                                # add time check for slowing down downloading.
                                # remember timing of each image for each camera
                                # currently set to 30 seconds - is plugin thread - so may make manually adjustable

                                if camera["BI_name"] in cameracheck:  # key in dict
                                    timecheck = cameracheck[cameraRequested]  # requested=BI_name here ##value
                                    if self.debug7:
                                        self.logger.debug("Found Camera name:{} in camera check with timevalue:{}".format(cameraRequested, timecheck))
                                    if t.time() - timecheck < 30:  ## 30 seconds update
                                        if self.debug7:
                                            self.logger.debug(" Skipping update as to soon, requested at timecheck difference {}".format(t.time() - timecheck))
                                        break
                                        # dont update timing
                                else:
                                    # cameracheck[cameraRequested] = t.time() ## new set the time and continue
                                    if self.debug7:
                                        self.logger.debug("Update Time for Camera {} to {}".format(cameraRequested, t.time()))

                                cameracheck[cameraRequested] = t.time()
                                camName = camera["BI_name"]
                                theURL = camera["BI_imageURL"] + "?w=" + str(image_width)
                                username = camera["BI_username"]
                                password = camera["BI_password"]
                                start = t.time()
                                path = self.cameraimagePath + '/' + camName + '.jpg'
                                if self.debug7:
                                    self.logger.debug("{}".format(path))
                                # r = r.get(theURL, auth=(str(username), str(password)), stream=True, timeout=10)
                                r = session.get(theURL, auth=(str(username), str(password)), stream=True, timeout=10)
                                # with open(path,"wb") as f:
                                #     f.write(r.content)
                                #     f.close()

                                if r.status_code == 200:
                                    with open(path, 'wb') as f:
                                        for chunk in r.iter_content(1024):
                                            f.write(chunk)
                                            if t.time() > (start + 10):
                                                self.logger.debug(u' Download Image Taking to long.  Aborted.')
                                                break
                                else:
                                    self.logger.debug("Camera Unavailable returning, Status Code:{}".format(r.status_code))
                                    self.logger.debug("Will pause downloading thread here for a few seconds")
                                    self.sleep(3)
                                if self.debug7:
                                    self.logger.debug("Downloaded Image for {}, with URL \n{}".format(camName, theURL))
                        elif "SS_name" in camera:
                            # self.logger.info("cameraREquested:{}  and canName:{}".format(cameraRequested, camera["BI_name"]))
                            if camera["SS_name"] == cameraRequested:
                                if self.debug7:
                                    self.logger.debug("Found matching Camera {} = {}".format(camera["SS_name"], cameraRequested))

                                # add time check for slowing down downloading.
                                # remember timing of each image for each camera
                                # currently set to 30 seconds - is plugin thread - so may make manually adjustable

                                if camera["SS_name"] in cameracheck:  # key in dict
                                    timecheck = cameracheck[cameraRequested]  # requested=BI_name here ##value
                                    if self.debug7:
                                        self.logger.debug("Found Camera name:{} in camera check with timevalue:{}".format(cameraRequested, timecheck))
                                    if t.time() - timecheck < 30:  ## 30 seconds update
                                        if self.debug7:
                                            self.logger.debug(" Skipping update as to soon, requested at timecheck difference {}".format(t.time() - timecheck))
                                        break
                                        # dont update timing
                                else:
                                    # cameracheck[cameraRequested] = t.time() ## new set the time and continue
                                    if self.debug7:
                                        self.logger.debug("Update Time for Camera {} to {}".format(cameraRequested, t.time()))

                                cameracheck[cameraRequested] = t.time()
                                camName = camera["SS_name"]
                                theURL = camera["SS_imageURL"] + "&width=" + str(image_width)
                                username = camera["SS_username"]
                                password = camera["SS_password"]
                                start = t.time()
                                path = self.cameraimagePath + '/' + camName + '.jpg'
                                if self.debug7:
                                    self.logger.debug("{}".format(path))
                                # r = r.get(theURL, auth=(str(username), str(password)), stream=True, timeout=10)
                                r = session.get(theURL, auth=(str(username), str(password)), stream=True, timeout=10)
                                # with open(path,"wb") as f:
                                #     f.write(r.content)
                                #     f.close()

                                if r.status_code == 200:
                                    with open(path, 'wb') as f:
                                        for chunk in r.iter_content(1024):
                                            f.write(chunk)
                                            if t.time() > (start + 10):
                                                self.logger.debug(u' Download Image Taking to long.  Aborted.')
                                                break
                                else:
                                    self.logger.debug("Error Downloading Camera Snashot, given Status Code:{}".format(r.status_code))
                                    self.logger.debug("Quite likely camera or Security Spy offline.  Having a slight pause for effect.")
                                    self.sleep(3)
                                if self.debug7:
                                    self.logger.debug("Downloaded Image for {}, with URL \n{}".format(camName, theURL))
                except:
                    self.logger.debug("exception in camera snapshots", exc_info=True)
        except self.StopThread:
            pass
        except:
            self.logger.debug("exception in camera snapShots", exc_info=True)
            pass

    ####################################################################################################################

    def startsingleBridge(self, device, uniqueID):
        try:
            self.logger.debug(f"Attempting to start a single Bridge:  Bridge {device.name} and ID {uniqueID}")
            ## Use list syntax -1 to use the last item added to list...
            ## Should allow lists to be added/removed and restarted....
            persist_file_location = os.path.join(self.pluginprefDirectory, 'busy_home_' + str(uniqueID) + '.state')
            # add port in use check
            # currentPortNumber - has now become starting portNumber - shoudl
            nextport = int(HKutils._find_next_available_port(self.startingPortNumber, self.portsinUse))
            self.logger.debug("Next Port available:{}".format(nextport))

            self.driver_multiple.append(HomeDriver(indigodeviceid=str(uniqueID),iid_storage=self.plugin_iidstorage, port=int(nextport), persist_file=persist_file_location, zeroconf_server=f"HomeKitLinkSiri-{uniqueID}-hap.local", async_zeroconf_instance=self.async_zeroconf_instance, address=self.HAPipaddress))

           # self.driver_multiple.append(HomeDriver(indigodeviceid=str(uniqueID), iid_storage=self.plugin_iidstorage, port=int(nextport), persist_file=persist_file_location))

            self.portsinUse.add(nextport)
            self.logger.debug("Sets of Ports Currently in Use: {}".format(self.portsinUse))
            self.bridge_multiple.append(HomeBridge(driver=self.driver_multiple[-1], plugin=self, indigodeviceid=uniqueID, display_name='HomeKitLink Bridge ' + str(uniqueID), iid_manager=HomeIIDManager(self.plugin_iidstorage, self.debug9)))
            self.driver_multiple[-1].add_accessory(accessory=self.get_bridge_multiple(self.driver_multiple[-1], self.bridge_multiple[-1], uniqueID))
            self.driverthread_multiple.append(threading.Thread(name=str(uniqueID), target=self.driver_multiple[-1].start, daemon=True))
            self.driverthread_multiple[-1].start()

            returned = self.bridge_multiple[-1].setup_message()
            self.logger.debug("Bridge {} Setup and Running.".format(uniqueID))
            updatedStates = [
                {'key': 'pincode', 'value': returned[1]},
                {'key': 'QRCode', 'value': returned[0]},
                {'key': "Status", 'value': "Operational"}
            ]
            device.updateStatesOnServer(updatedStates)
            device.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            self.sleep(0.5)
            if len(self.listofenabledcameras) > 0:
                self.logger.debug("Camera Accessory Found, checking single thread is alive to manage images.")
                self.start_CameraSnapshots()
        except:
            self.logger.exception("Exception in single Bridge Startup")
            device.updateStatesOnServer(key="status", value="Error")
            device.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
            device.setErrorStateOnServer("Failure to Start Bridge.")

    # Get XML child element from dom
    # Thanks Colorado4Wheeler - https://github.com/Colorado4Wheeler/HomeKit-Bridge/blob/master/EPS%20HomeKit%20Bridge.indigoPlugin/Contents/Server%20Plugin/plugin.py
    #
    def _getChildElementsByTagName(self, elem, tagName):
        try:
            childList = []
            for child in elem.childNodes:
                if child.nodeType == child.ELEMENT_NODE and (tagName == u"*" or child.tagName == tagName):
                    childList.append(child)
            return childList
        except:
            self.logger.debug("Exception in childElement")

    #
    # Get value of element from dom
    #
    def _getElementValueByTagName(self, elem, tagName, required=True, default=None, filename=u"unknown"):
        try:
            valueElemList = self._getChildElementsByTagName(elem, tagName)
            if len(valueElemList) == 0:
                if required:
                    raise ValueError(u"required XML element <%s> is missing in file %s" % (tagName, filename))
                return default
            elif len(valueElemList) > 1:
                raise ValueError(u"found more than one XML element <%s> (should only be one) in file %s" % (tagName, filename))

            valueStr = valueElemList[0].firstChild.data
            if valueStr is None or len(valueStr) == 0:
                if required:
                    raise ValueError(u"required XML element <%s> is empty in file %s" % (tagName, filename))
                return default
            return valueStr
        except:
            self.logger.debug("Exception in ElementValuebyTagName")

    #
    def get_CameraOptions(self, indigodeviceid):
        if self.debug7:
            self.logger.debug("sorting out camera options for ID:{}".format(indigodeviceid))
        config = {}


        try:
            if indigo.devices[indigodeviceid].pluginId == "com.GlennNZ.indigoplugin.BlueIris":
                # config["support_audio"] = True
                biDev = indigo.devices[indigodeviceid]
                biWidth = biDev.states["width"]
                biHeight = biDev.states["height"]
                biName = biDev.states["optionValue"]
                biFPS = 15  # int(biDev.states["FPS"])

                supportAudio = biDev.pluginProps.get("HomeKit_audioSelector", False)

                config["support_audio"] = supportAudio
                config["BI_name"] = biDev.states["optionDisplay"]
                config["BI_camName"] = biName

                prefFile = '{}/Preferences/Plugins/com.GlennNZ.indigoplugin.BlueIris.indiPref'.format(indigo.server.getInstallFolderPath())
                biServerIp = ""
                biPort = ""
                biUser = ""
                biPass = ""

                if os.path.isfile(prefFile):
                    file = open(prefFile, 'r')
                    prefdata = file.read()
                    dom = xml.dom.minidom.parseString(prefdata)
                    prefs = self._getChildElementsByTagName(dom, u"Prefs")
                    biServerIp = self._getElementValueByTagName(prefs[0], u"serverip", required=False, default=u"")
                    biPort = self._getElementValueByTagName(prefs[0], u"serverport", required=False, default=u"")
                    biUser = self._getElementValueByTagName(prefs[0], u"serverusername", required=False, default=u"")
                    biPass = self._getElementValueByTagName(prefs[0], u"serverpassword", required=False, default=u"")

                    if biPass == "":
                        biURLrtsp = u"rtsp://{}:{}".format(biServerIp, biPort)
                        biURLhttp = u"http://{}:{}".format(biServerIp, biPort)
                    else:
                        biURLrtsp = u"rtsp://{}:{}@{}:{}".format(biUser, biPass, biServerIp, biPort)
                        biURLhttp = u"http://{}:{}@{}:{}".format(biUser, biPass, biServerIp, biPort)
                file.close()

                if biFPS <= 2: biFPS = 15

                config[HKDevicesCamera.CONF_VIDEO_CODEC] = "copy"  # "openh264" #HKDevicesCamera.DEFAULT_VIDEO_CODEC
                config[HKDevicesCamera.CONF_AUDIO_CODEC] = "libfdk_aac"  # "aac"
                config[HKDevicesCamera.CONF_MAX_HEIGHT] = biHeight
                config[HKDevicesCamera.CONF_MAX_WIDTH] = biWidth
                config[HKDevicesCamera.CONF_MAX_FPS] = int(biFPS)
                config[HKDevicesCamera.CONF_VIDEO_MAP] = "0:0"

                config["DoorBell_ID"] = indigo.devices[indigodeviceid].pluginProps.get("HomeKit_doorbellId", "")
                config["BI_serverip"] = biServerIp
                config["BI_serverport"] = biPort
                config["BI_username"] = biUser
                config["BI_password"] = biPass
                config["BI_imageURL"] = "{}/image/{}".format(biURLhttp, biName)

                config["useMotionSensor"] = True
                config["start_commands_extra"] = ("-rtsp_transport tcp "
                                                  "-probesize 32 "
                                                  "-analyzeduration 0 ")
                config[HKDevicesCamera.CONF_STREAM_SOURCE] = '{}/{}&stream=2&fps=15'.format(biURLrtsp, biName)

            elif indigo.devices[indigodeviceid].pluginId == "org.cynic.indigo.securityspy":
                # Get the device and it's SS server
                ssDev = indigo.devices[indigodeviceid]
                ssServerId, ssCameraNum = ssDev.ownerProps["xaddress"].split("@")
                supportAudio = ssDev.pluginProps.get("HomeKit_audioSelector", False)
                config["support_audio"] = supportAudio
                ssServer = indigo.devices[int(ssServerId)]
                ssWidth = 640
                ssHeight = 480
                ssFPS = 30
                ssUsername = "{}".format(ssServer.ownerProps["username"])
                ssPassword = "{}".format(ssServer.ownerProps["password"])
                ssuPw = u"{}:{}@".format(ssServer.ownerProps["username"], ssServer.ownerProps["password"])
                if ssServer.ownerProps["password"] == "": ssuPw = ""
                ssURL = u"http://{}{}:{}".format(ssuPw, ssServer.ownerProps["xaddress"], ssServer.ownerProps["port"])
                ssURL_rtsp = "rtsp://{}{}:{}".format(ssuPw, ssServer.ownerProps["xaddress"], ssServer.ownerProps["port"])
                if ssServer.ownerProps["xaddress"] == "":
                    ssURL = u"http://{}{}".format(ssuPw, ssServer.ownerProps["address"])
                    ssURL_rtsp = "rtsp://{}{}:{}".format(ssuPw, ssServer.ownerProps["address"], ssServer.ownerProps["port"])

                ssSystem = u"{}/++systemInfo".format(ssURL)
                try:
                    response = requests.get(ssSystem, timeout=5)  # Pull XML data
                except:
                    self.logger.debug("Exception Camera offline",exc_info=True)
                    return None

                data = response.content
                ssName = ssDev.name
                # Extract XML data
                dom = xml.dom.minidom.parseString(data)
                system = self._getChildElementsByTagName(dom, u"system")
                sscameralist = self._getChildElementsByTagName(system[0], u"cameralist")
                sscameras = self._getChildElementsByTagName(sscameralist[0], u"camera")

                # Get the width and height from XML dta
                for sscamera in sscameras:
                    try:
                        number = self._getElementValueByTagName(sscamera, u"number", required=False, default=u"")
                        if int(number) == int(ssCameraNum):
                            ssWidth = int(self._getElementValueByTagName(sscamera, u"width", required=False, default=u""))
                            ssHeight = int(self._getElementValueByTagName(sscamera, u"height", required=False, default=u""))
                            ssFPS = int(float(self._getElementValueByTagName(sscamera, u"current-fps", required=False, default=u"")))
                            ssName = str(self._getElementValueByTagName(sscamera, u"name", required=False, default=u""))
                            if ssFPS < 10: ssFPS = 10
                            break
                    except:
                        self.logger.warning(u"Unable to retrieve SecuritySpy parameters for {}, defaulting to {}x{} and {} FPS".format(ssDev.name, ssWidth, ssHeight, ssFPS))

                config[HKDevicesCamera.CONF_VIDEO_CODEC] = "libx264"  # "libx264"  # "openh264" #HKDevicesCamera.DEFAULT_VIDEO_CODEC
                config[HKDevicesCamera.CONF_AUDIO_CODEC] = "libfdk_aac"  # "aac"
                config[HKDevicesCamera.CONF_MAX_HEIGHT] = ssHeight
                config[HKDevicesCamera.CONF_MAX_WIDTH] = ssWidth
                config[HKDevicesCamera.CONF_MAX_FPS] = int(ssFPS)
                config[HKDevicesCamera.CONF_VIDEO_MAP] = "0:0"

                config["DoorBell_ID"] = indigo.devices[indigodeviceid].pluginProps.get("HomeKit_doorbellId", "")
                config["SS_name"] = ssName
                config["SS_serverip"] = ssServer.ownerProps["xaddress"]
                config["SS_serverport"] = ssServer.ownerProps["port"]
                config["SS_username"] = ssUsername
                config["SS_password"] = ssPassword
                # config["SS_username_pass"] = ssuPw
                config["SS_imageURL"] = "{}/++image?cameraNum={}".format(ssURL, ssCameraNum)
                config["useMotionSensor"] = True
                config["start_commands_extra"] = ("-rtsp_transport tcp "  # )
                                                  #           "-fflags +igndts ")
                                                  #
                                                  "-probesize 64 "
                                                  "-analyzeduration 0 ")
                #      config[HKDevicesCamera.CONF_STREAM_SOURCE] = "{}/++video?cameraNum={}&width={}&height={}".format(ssURL, ssCameraNum, ssWidth, ssHeight)

                if ssWidth > 1280:
                    ssWidth = 1280
                config[HKDevicesCamera.CONF_STREAM_SOURCE] = "{}/stream?cameraNum={}&width={}".format(ssURL_rtsp, ssCameraNum, ssWidth)

            else:  # Yikes not a camera
                self.logger.warning("This device ID {} with Name {} ** CANNOT ** be a camera device in HomeKit. Please remove and update. ".format(indigodeviceid, indigo.devices[indigodeviceid].name))
                return None
            # Create Default Image for Accessory at beginning to avoid filenotfound exception (caught)
            # later on.
            try:
                CameraName = ""
                if "BI_name" in config:
                    CameraName = config["BI_name"]
                elif "SS_name" in config:
                    CameraName = config["SS_name"]
                if CameraName != "":
                    path = self.cameraimagePath + "/" + CameraName + ".jpg"
                    # path = self.pluginPath + '/cameras/' + CameraName + '.jpg'
                    snapshot_path = self.pluginPath + "/cameras/snapshot.jpg"
                    shutil.copy(snapshot_path, path)
                    if self.debug7:
                        self.logger.debug("Startup Refresh Snapshots images to Default for Camera: {}".format(path))
            except:
                self.logger.debug("Caught Exception in defaulting Camera Snapshot at creation")

            self.logger.debug("Config Now\n{}\n".format(config))
            return config

        except:
            self.logger.info("Error adding this Camera Accessory. with Indigo ID {}".format(indigodeviceid))
            self.logger.info("Accessory has been disabled currently.  Question BlueIris or Security Spy up and running?")
            self.logger.debug("Caught Exception get Camera Options: Return Error", exc_info=True)
            return None  ## move to Camera Init

    def update_deviceList(self):
        self.count = 0
        listid = []
        for dev in indigo.devices:
            if dev.pluginProps.get("HomeKit_publishDevice", False):
                try:
                    self.count += 1
                    if (dev.id in listid) == False:
                        listid.append(dev.id)
                        self.device_list.add(dev.id)
                        # self.logger.debug(u"... '{}' published".format(dev.name))
                    else:
                        self.logger.error("Duplicate ID Skipped")
                except:
                    self.logger.exception("Startup Publish.")
        for dev in indigo.actionGroups:
            if dev.pluginProps.get("HomeKit_publishDevice", False):
                try:
                    self.count += 1
                    if (dev.id in listid) == False:
                        listid.append(dev.id)
                        self.device_list.add(dev.id)
                        # self.logger.debug(u"... Action Group: '{}' published".format(dev.name))
                    else:
                        self.logger.error("Duplicate ID Skipped")
                except:
                    self.logger.exception("Startup Publish.")

    def _check_cameraDir(self):
        if not os.path.exists(self.pluginprefDirectory):
            os.makedirs(self.pluginprefDirectory)
        camerapath = os.path.join(self.pluginprefDirectory, "cameras")
        if not os.path.exists(camerapath):
            os.makedirs(camerapath)


    def startup(self):
        self.debugLog(u"Starting Plugin. startup() method called.")
        self.device_list = set()  ## NB this is list of devices wished to be seen in HomeKit, self_device_list_internal - is list of Devices actually published
        self.logger.info('Finding devices to publish to HomeKit Given Startup...')
        self.logger.debug("Checking Plugin Prefs Directory")

        ## Create Prefs Directory and Camera for images directory
        self._check_cameraDir()
        camerapath = os.path.join(self.pluginprefDirectory, "cameras")
        self.cameraimagePath = camerapath

        self.logger.debug("Saving Camera Snapshots to:{}".format(self.cameraimagePath))
        self.update_deviceList()
        indigo.devices.subscribeToChanges()
        self.create_deviceList_internal()

        self.plugin_iidstorage = AccessoryIIDStorage(self.pluginId, self.pluginprefDirectory+str("/AccessoryIIDStorage.storage"), self.debug9 )
        self.plugin_iidstorage.startup()

    def shutdown(self):
        self.logger.info("Shutting down HomeKitLink")

    ### Subscription Changes
    ########################################
    '''
    deviceUpdate - receives update from all Indigo Devices.  Checks again list of device.id (HK published/active devices)
    If matches - check index of self.internal_device_list list to find appropriate accessory we wish to control
    Then depending on device and matches -- send back to accessory value/data based on this change
    This with plugin_getter and plugin_setter (which accessory class call) are the mainstay of 2 way information
    The plugin side is doing most of the data checking - but limiting factor would be deviceUpdated catching everything even if could async off
    '''

    ########################################
    def deviceDeleted(self, deleted_device):
        # Watch for any devices that we care about and see if we need to push a change up to HomeKit
        super(Plugin, self).deviceDeleted(deleted_device)

        try:
            if deleted_device.id in self.device_list_internal_idonly:
                # It's one we care about
                checkindex = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == deleted_device.id), None)
                if checkindex != None:
                    self.logger.info("Deleting item:{}".format(self.device_list_internal[checkindex]))
                    del self.device_list_internal[checkindex]
                    # it should be in this below list as should match above only containing IDs
                    if deleted_device.id in self.device_list_internal_idonly:
                        self.device_list_internal_idonly.remove(deleted_device.id)
                self.logger.error("Device: {} ,just deleted published and has active accessory within Homekit currently (!)".format(deleted_device.name))
                try:
                    bridgeID = int(deleted_device.pluginProps.get("HomeKit_bridgeUniqueID", 99))
                except ValueError:
                    bridgeID = 99
                if bridgeID != 99:
                    self.logger.info("Deleted Device appears to be running of Bridge {}.  Attempting to restart Bridge and reset all Accessories.".format(bridgeID))
                    for device in indigo.devices.iter("self"):
                        # if device.enabled:  ## enabled or disabled if exists want to save state file
                        uniqueID = device.pluginProps.get("bridgeUniqueID", 99)
                        if int(uniqueID) == int(bridgeID):
                            # matching device found
                            indigo.device.enable(device.id, False)
                            ## Turn off
                            self.sleep(1)  ##  given async exit probably needs this
                            indigo.device.enable(device.id, True)

            if deleted_device.id in self.device_list:
                ## this is list of all wished to published devices, event those off/not currently enabled for example.
                ## this list is created on startup - but delete here
                self.device_list.remove(deleted_device.id)
                self.logger.debug("Device: {} ,just deleted published and within Homekit, will likely need appropriate Bridge Restarted.".format(deleted_device.name))
        except:
            self.logger.debug("Caught Exception in Delete Device", exc_info=True)

    ########################################

    def deviceUpdated(self, original_device, updated_device):

        ## Below checks for device in device list and if device updated, then update its states
        #  Question is whether I send this quickly back to Accessory to 'process' in a async fashion
        #  May be quicker?  May be less customisable/selectable though, errors in Accessory harder to trace/tend to crash
        #  Plugin here still will have to receive device updates.. so very marginally checking happening
        #

        try:
            super(Plugin, self).deviceUpdated(original_device, updated_device)

            if self.pluginStartingUp:
                self.logger.debug("Still starting up. Ignoring device update")
                return
            if original_device.id not in self.device_list_internal_idonly:
                return

            this_is_debug_device = False
            checkindex = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == original_device.id), None)

            if checkindex != None:
                if self.debug2:
                    self.logger.debug("Device Changed that interested in...{}".format(original_device.name))
                    self.logger.debug("Device Found in Device List. CheckIndex Key Exists :{}".format(checkindex))
                if self.debug2:
                    self.logger.debug("Subtype:{}, and type(original_device):{} & devicesensor:{}".format(
                        self.device_list_internal[checkindex]["subtype"], type(original_device),
                        self.device_list_internal[checkindex]["devicesensor"]))
                ## Debug Device Update Found.
                if self.debugDeviceid == original_device.id:
                    self.logger.warning("{0:=^130}".format(" Device Selected for Logging "))
                    self.logger.warning(f"Original Device States:\n{original_device.states} ")
                    self.logger.warning(f"Updated Device States: \n{updated_device.states} ")
                    this_is_debug_device = True

                updateddevice_subtype = self.device_list_internal[checkindex]["subtype"]

                if str(updateddevice_subtype) == "Thermostat":
                    if self.debug2:
                        self.logger.debug("Found Thermostat Matching Device...")
                    if this_is_debug_device:
                        self.logger.info("Found Thermostat Matching Device...")
                    if hasattr(updated_device, "temperatures"):  ## double check here in
                        if original_device.temperatures != updated_device.temperatures:
                            listtemps = updated_device.temperatures
                            if isinstance(listtemps, list):
                                temptosend = sum(listtemps) / len(listtemps)  ##average of all values
                            elif isinstance(listtemps, (float, int)):
                                temptosend = listtemps
                            else:
                                temptosend = 1.3
                            if self.debug2:
                                self.logger.debug("Updating Temperature to {}".format(temptosend))
                            if this_is_debug_device:
                                self.logger.warning("Updating Temperature to {}".format(temptosend))
                            # add conversion for F disable to test TODO big
                            self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(temptosend), "current")
                            # self.device_list_internal[checkindex]["accessory"].char_current_temp.set_value(HKutils.convert_to_float(temptosend))

                    if hasattr(updated_device, "hvacMode"):  ## double check here in
                        if original_device.hvacMode != updated_device.hvacMode:
                            ## set target mode when hvacMode changes
                            newmode = updated_device.hvacMode
                            listHvacModes = {indigo.kHvacMode.Off: 0,
                                             indigo.kHvacMode.Heat: 1,
                                             indigo.kHvacMode.Cool: 2,
                                             indigo.kHvacMode.HeatCool: 3}
                            homekitModeWished = listHvacModes[newmode]
                            self.device_list_internal[checkindex]["accessory"].char_target_heat_cool.set_value(homekitModeWished)

                            ## Mode has been changed need to update target and range for HomeKit
                            if 'setpointCool' in updated_device.states:
                                setpointcool = updated_device.states['setpointCool']
                                setpointheat = updated_device.states['setpointHeat']
                                if updated_device.hvacMode == indigo.kHvacMode.Off:
                                    pass
                                elif updated_device.hvacMode == indigo.kHvacMode.Heat:
                                    ## set targettemp to setpointHeat
                                    self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointheat), "target")
                                elif updated_device.hvacMode == indigo.kHvacMode.Cool:
                                    ## set targettemp to setpointHeat
                                    self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointcool), "target")
                                elif updated_device.hvacMode == indigo.kHvacMode.HeatCool:
                                    ## set targettemp to setpointHeat
                                    self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointcool), "coolthresh")
                                    self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointheat), "heatthresh")
                            ## Given mode change also change the current setting depending on heater cooler mode immediately
                            if updated_device.hvacMode == indigo.kHvacMode.Off:
                                if self.debug2:
                                    self.logger.debug(f"hvacMode == Off")
                                self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                            elif updated_device.hvacMode == indigo.kHvacMode.Heat:
                                ## set targettemp to setpointHeat
                                if self.debug2:
                                    self.logger.debug(f"hvacMode == Heat and current Heater is {updated_device.states['hvacHeaterIsOn']}")
                                if 'hvacHeaterIsOn' in updated_device.states:
                                    if updated_device.states["hvacHeaterIsOn"]==True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(1)
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                            elif updated_device.hvacMode == indigo.kHvacMode.Cool:
                                if self.debug2:
                                    self.logger.debug(f"hvacMode == Cool and current Cooler is {updated_device.states['hvacCoolerIsOn']}")
                                if 'hvacCoolerIsOn' in updated_device.states:
                                    if updated_device.states["hvacCoolerIsOn"] == True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(2)
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)  #cooling
                            elif updated_device.hvacMode == indigo.kHvacMode.HeatCool:
                                ## set targettemp to setpointHeat
                                if self.debug2:
                                    self.logger.debug(f"hvacMode == HeatCool and current Cooler is {updated_device.states['hvacCoolerIsOn']}, and Heater is {updated_device.states['hvacHeaterIsOn']}")
                                if 'hvacCoolerIsOn' in updated_device.states:
                                    if updated_device.states["hvacCoolerIsOn"] == True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(2)
                                    elif updated_device.states["hvacHeaterIsOn"] == True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(1)  #cooling
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                            if this_is_debug_device:
                                self.logger.warning("Setting Target and Current Mode of Hvac. Mode Wished. {}".format(homekitModeWished))
                            if self.debug2:
                                self.logger.debug("Thermostat Device has been changed, updating all temp targets/setpoints")

                        if 'hvacHeaterIsOn' in updated_device.states and 'hvacCoolerIsOn' in updated_device.states:
                            if updated_device.states["hvacHeaterIsOn"] != original_device.states["hvacHeaterIsOn"] or updated_device.states["hvacCoolerIsOn"] != original_device.states["hvacCoolerIsOn"] :
                                ## current allowed 0,1,2 only
                                ## target allowed
                                if self.debug2:
                                    self.logger.debug("Thermostat Device Heater On or Cooler On has changed.  Updating.")
                                '''
                                Current
                                     "Cool": 2,
                                     "Heat": 1,
                                     "Off": 0
                                Target
                                    "Auto": 3,
                                    "Cool": 2,
                                    "Heat": 1,
                                    "Off": 0
                                '''
                                # if homekitModeWished != 3:
                                #     # if not auto set to heat or cool or 0
                                #     self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(homekitModeWished)
                                #     # Crashed Home Kit with no error message
                                #     # add ability for fan idle if temp reached - well attempt to.  Seems from this and below code block doesn't occur in auto modes
                                #
                                # else:
                                    # if auto - is the hvac heating or cooling currently..  Use Image selector...
                                if updated_device.hvacMode == indigo.kHvacMode.Off:
                                    if self.debug2:
                                        self.logger.debug(f"hvacMode == Off")
                                    self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                                elif updated_device.hvacMode == indigo.kHvacMode.Heat:
                                    ## set targettemp to setpointHeat
                                    if self.debug2:
                                        self.logger.debug(f"hvacMode == Heat and current Heater is {updated_device.states['hvacHeaterIsOn']}")
                                    if updated_device.states["hvacHeaterIsOn"]==False:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(1)
                                elif updated_device.hvacMode == indigo.kHvacMode.Cool:
                                    if self.debug2:
                                        self.logger.debug(f"hvacMode == Cool and current Cooler is {updated_device.states['hvacCoolerIsOn']}")
                                    if updated_device.states["hvacCoolerIsOn"] == False:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(2)  #cooling
                                elif updated_device.hvacMode == indigo.kHvacMode.HeatCool:
                                    ## set targettemp to setpointHeat
                                    if self.debug2:
                                        self.logger.debug(f"hvacMode == HeatCool and current Cooler is {updated_device.states['hvacCoolerIsOn']}, and Heater is {updated_device.states['hvacHeaterIsOn']}")
                                    if updated_device.states["hvacCoolerIsOn"] == True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(2)
                                    elif updated_device.states["hvacHeaterIsOn"] == True:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(1)  #cooling
                                    else:
                                        self.device_list_internal[checkindex]["accessory"].char_current_heat_cool.set_value(0)


                    if "setpointCool" in updated_device.states:
                        self.logger.debug(f"setpointCool Found: Original: {original_device.states['setpointCool']} and updated:  {updated_device.states['setpointCool']} ")
                        if original_device.states["setpointCool"] != updated_device.states["setpointCool"]:
                            setpointCool = updated_device.states["setpointCool"]
                            if self.debug2:
                                self.logger.debug("Updating setpointCool to {}".format(setpointCool))
                            if this_is_debug_device:
                                self.logger.warning("Updating setpointCool to {}".format(setpointCool))
                            self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointCool), "setpointCool")
                    if "setpointHeat" in updated_device.states:
                        if original_device.states["setpointHeat"] != updated_device.states["setpointHeat"]:
                            setpointHeat = updated_device.states["setpointHeat"]
                            if self.debug2:
                                self.logger.debug("Updating setpointHeat to {}".format(setpointHeat))
                            if this_is_debug_device:
                                self.logger.warning("Updating setpointHeat to {}".format(setpointHeat))
                            self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(setpointHeat), "setpointHeat")

                elif str(updateddevice_subtype) in ("TemperatureSensor", "HumiditySensor", "LightSensor"):  # , "OccupancySensor", "ContactSensor", "CarbonDioxideSensor"):  ## example of one way sesnor
                    if type(original_device) == indigo.SensorDevice:
                        sensortouse = self.device_list_internal[checkindex]["devicesensor"]
                        if sensortouse != "sensorValue":
                            if sensortouse != "":
                                if sensortouse in updated_device.states:
                                    ## add below check for this state after changed
                                    if updated_device.states[sensortouse] != original_device.states[sensortouse]:
                                        sensorvalue = HKutils.convert_to_float(updated_device.states[sensortouse])
                                        if type(sensorvalue) in (float, int):
                                            if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                                sensorvalue = 100000
                                        if self.debug2:
                                            self.logger.debug("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))
                                        if this_is_debug_device:
                                            self.logger.warning("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))

                                        if str(updateddevice_subtype) == "TemperatureSensor":
                                            if this_is_debug_device:
                                                self.logger.warning("Temperature Sensor found, sending to HKAccessory to convert.  Current Sensorvalue {}".format(sensorvalue))
                                            self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(sensorvalue))
                                        else:
                                            if this_is_debug_device:
                                                self.logger.warning("Humidty or Light Sensor found, Sending Sensorvalue {}".format(sensorvalue))
                                            self.device_list_internal[checkindex]["accessory"].char_temp.set_value(HKutils.convert_to_float(sensorvalue))
                        else:
                            if "sensorValue" in updated_device.states:
                                if original_device.states["sensorValue"] != updated_device.states["sensorValue"]:
                                    sensorvalue = HKutils.convert_to_float(updated_device.states["sensorValue"])
                                    if type(sensorvalue) in (float, int):
                                        if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                            sensorvalue = 100000
                                    if self.debug2:
                                        self.logger.debug("Device {} + SensorValue:{} + type(sensorValue) {}".format(
                                            updated_device.name, sensorvalue, type(sensorvalue)))
                                    if this_is_debug_device:
                                        self.logger.warning("Device {} + SensorValue:{} + type(sensorValue) {}".format(
                                            updated_device.name, sensorvalue, type(sensorvalue)))
                                    if self.debug1:
                                        self.logger.debug("Found a Sensor value, using that")
                                    if str(updateddevice_subtype) == "TemperatureSensor":
                                        if this_is_debug_device:
                                            self.logger.warning("Temperature Sensor found, sending to HKAccessory to convert.  Current Sensorvalue {}".format(sensorvalue))
                                        self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(sensorvalue))
                                    else:
                                        if this_is_debug_device:
                                            self.logger.warning("Humidty or Light Sensor found, Sending Sensorvalue {}".format(sensorvalue))
                                        self.device_list_internal[checkindex]["accessory"].char_temp.set_value(HKutils.convert_to_float(sensorvalue))

                                    #self.device_list_internal[checkindex]["accessory"].char_temp.set_value(sensorvalue)  ##CurrentTemperature is chartemp
                        ## else check internal list for sensor State that we wish to return back
                    else:
                        sensortouse = self.device_list_internal[checkindex]["devicesensor"]
                        if sensortouse != "":
                            if sensortouse in updated_device.states:
                                if updated_device.states[sensortouse] != original_device.states[sensortouse]:
                                    sensorvalue = HKutils.convert_to_float(updated_device.states[sensortouse])
                                    if type(sensorvalue) in (float, int):
                                        if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                            sensorvalue = 100000
                                    if self.debug2:
                                        self.logger.debug(
                                            "Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(
                                                updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))

                                    if this_is_debug_device:
                                        self.logger.debug("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(
                                            updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))
                                    if str(updateddevice_subtype) == "TemperatureSensor":
                                        if this_is_debug_device:
                                            self.logger.warning("Temperature Sensor found, sending to HKAccessory to convert.  Current Sensorvalue {}".format(sensorvalue))
                                        self.device_list_internal[checkindex]["accessory"].set_temperature(HKutils.convert_to_float(sensorvalue))
                                    else:
                                        if this_is_debug_device:
                                            self.logger.warning("Humidty or Light Sensor found, Sending Sensorvalue {}".format(sensorvalue))
                                        self.device_list_internal[checkindex]["accessory"].char_temp.set_value(HKutils.convert_to_float(sensorvalue))

                    # sensor type updated and check Battery
                    if "batteryLevel" in updated_device.states:
                        if not self.device_list_internal[checkindex]["accessory"]._char_battery or not self.device_list_internal[checkindex]["accessory"]._char_low_battery:
                            if updated_device.states["batteryLevel"] != original_device["batteryLevel"]:
                                batteryLevel = HKutils.convert_to_float(updated_device.states["batteryLevel"])
                                if batteryLevel is not None:
                                    self.device_list_internal[checkindex]["accessory"]._char_battery.set_value(batteryLevel)
                                    is_low_battery = 1 if batteryLevel < self.low_battery_threshold else 0
                                    self._char_low_battery.set_value(is_low_battery)
                                    if self.debug2:
                                        self.logger.debug( "{}: Updated battery level to {}".format(updated_device.name, batteryLevel) )


                elif str(updateddevice_subtype) in ("LeakSensor", "OccupancySensor", "SmokeSensor", "ContactSensor", "CarbonMonoxideSensor", "CarbonDioxideSensor"):  ## example of one way sesnor
                    if type(original_device) == indigo.SensorDevice:
                        sensortouse = self.device_list_internal[checkindex]["devicesensor"]
                        if sensortouse != "sensorValue":
                            if sensortouse != "":
                                if sensortouse in updated_device.states:
                                    if updated_device.states[sensortouse] != original_device.states[sensortouse]:
                                        sensorvalue = updated_device.states[sensortouse]
                                        if self.debug2:
                                            self.logger.debug("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))
                                        if this_is_debug_device:
                                            self.logger.warning("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))
                                        self.device_list_internal[checkindex]["accessory"].char_on.set_value(sensorvalue)
                        else:
                            if "sensorValue" in updated_device.states:
                                if original_device.states["sensorValue"] != updated_device.states["sensorValue"]:
                                    sensorvalue = updated_device.states["sensorValue"]
                                    if self.debug2:
                                        self.logger.debug("Device {} + sensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensorvalue, type(sensorvalue)))
                                    if this_is_debug_device:
                                        self.logger.warning("Device {} + sensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensorvalue, type(sensorvalue)))

                                    self.device_list_internal[checkindex]["accessory"].char_on.set_value(sensorvalue)  ##CurrentTemperature is chartemp
                        ## else check internal list for sensor State that we wish to return back
                    else:
                        sensortouse = self.device_list_internal[checkindex]["devicesensor"]
                        if sensortouse != "":
                            if sensortouse in updated_device.states:
                                if updated_device.states[sensortouse] != original_device.states[sensortouse]:
                                    sensorvalue = updated_device.states[sensortouse]
                                    if self.debug2:
                                        self.logger.debug("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))
                                    if this_is_debug_device:
                                        self.logger.warning("Device {} ,SensortoUse {} SensorValue:{} + type(sensorValue) {}".format(updated_device.name, sensortouse, sensorvalue, type(sensorvalue)))

                                    self.device_list_internal[checkindex]["accessory"].char_on.set_value(sensorvalue)
                    # sensor type updated and check Battery
                    if "batteryLevel" in updated_device.states:
                        if not self.device_list_internal[checkindex]["accessory"]._char_battery or not self.device_list_internal[checkindex]["accessory"]._char_low_battery:
                            if updated_device.states["batteryLevel"] != original_device["batteryLevel"]:
                                batteryLevel = HKutils.convert_to_float(updated_device.states["batteryLevel"])
                                if batteryLevel is not None:
                                    self.device_list_internal[checkindex]["accessory"]._char_battery.set_value(batteryLevel)
                                    is_low_battery = 1 if batteryLevel < self.low_battery_threshold else 0
                                    self._char_low_battery.set_value(is_low_battery)
                                    if self.debug2:
                                        self.logger.debug( "{}: Updated battery level to {}".format(updated_device.name, batteryLevel) )

                elif str(updateddevice_subtype) == "Lock" :  ## example of one way sesnor
                    # if type(original_device) == indigo.RelayDevice:
                    if updated_device.states['onOffState'] != original_device.states['onOffState']:
                        newstate = updated_device.states["onOffState"]
                        if self.debug2:
                            self.logger.debug("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        if this_is_debug_device:
                            self.logger.warning("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        self.device_list_internal[checkindex]["accessory"].char_target_state.set_value(newstate)
                        self.device_list_internal[checkindex]["accessory"].char_current_state.set_value(newstate)
                        return
                    elif "lastChangedVia" in updated_device.states and updated_device.states['lastChangedVia'] != original_device.states['lastChangedVia']:
                        ## Locks send Onoffstate, and then lastchangedvia update.
                        ## homekit appears to like some time between target and current
                        ## below here - resend back to homekit update on this other trigger.
                        newstate = updated_device.states["onOffState"]
                        if self.debug2:
                            self.logger.debug("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        if this_is_debug_device:
                            self.logger.warning("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        self.device_list_internal[checkindex]["accessory"].char_target_state.set_value(newstate)
                        self.device_list_internal[checkindex]["accessory"].char_current_state.set_value(newstate)

                elif str(updateddevice_subtype) == "Security":
                    if updated_device.states != original_device.states:
                        if self.debug2:
                            self.logger.debug("NewState of Device:{} & State: {} ".format(updated_device.name, updated_device.states))
                        if this_is_debug_device:
                            self.logger.warning("NewState of Device:{} & State: {} ".format(updated_device.name, updated_device.states))

                        if self.device_list_internal[checkindex]['manufacturername'] == "com.frightideas.indigoplugin.dscAlarm":
                            if "state" in updated_device.states:
                                if updated_device.states['state'] != original_device.states['state']:  # focusing only on changes of 'state' (not LED, Time etc)
                                    self.device_list_internal[checkindex]["accessory"].set_fromdeviceUpdate(updated_device.states)
                        else:
                            self.device_list_internal[checkindex]["accessory"].set_fromdeviceUpdate(updated_device.states)
                        return

                elif str(updateddevice_subtype) == "GarageDoor":
                    for stateName in ("doorState", "onOffState", "binaryInput1"):  # ordered by preference
                        # doorState:    0 -> open, 1 -> closed, 2 -> opening, 3 -> closing, 4 -> stopped, 5 -> reversing
                        # onOffState:   0 -> open, 1 -> closed
                        # binaryInput1: 0 -> open, 1 -> closed
                        if stateName in updated_device.states:  # choose the first match
                            oldstate = original_device.states[stateName]
                            newstate = updated_device.states[stateName]
                            if newstate != oldstate:  # state has changed
                                # Log Indigo device state change.
                                # (VGD) debug code for papamac's Virtual Garage Door (VGD) changes
                                # (VGD) self.logger.warning('Indigo device "{}" {} changed: {} --> {}'.format(updated_device.name, stateName, oldstate, newstate))
                                if self.debug2:
                                    self.logger.debug("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                                if this_is_debug_device:
                                    self.logger.warning("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                                accessory = self.device_list_internal[checkindex]["accessory"]
                                # (VGD) oldChars = self._getGarageDoorCharacteristics(accessory)

                                # Update GarageDoor characteristics based on Indigo device state change.

                                # CurrentDoorState must be 0 -> open, 1 -> closed, 2 -> opening, or 3 -> closing.
                                currentDoorState = (0, 1, 2, 3, 0, 2)[newstate]
                                accessory.char_current_state.set_value(currentDoorState)

                                # TargetDoorState must be 0 -> open or 1 -> closed
                                targetDoorState = (0, 1, 0, 1, 0, 0)[newstate]
                                accessory.char_target_state.set_value(targetDoorState)

                                # ObstructionDetected must be 0 -> False or 1 -> True
                                obstructionDetected = (None, 0, None, None, 1, 1)[newstate]
                                if obstructionDetected is not None:
                                    accessory.char_obstruction_detected.set_value(obstructionDetected)

                                # (VGD) newChars = self._getGarageDoorCharacteristics(accessory)
                                # (VGD) self.logger.warning('GarageDoor characteristics changed by HKLS (c, t, o): {} --> {}'.format(oldChars, newChars))
                            break
                    return

                elif str(updateddevice_subtype) in ("Valve","Irrigation","Showerhead","Faucet"):
                    # if type(original_device) == indigo.RelayDevice:
                    if updated_device.states['onOffState'] != original_device.states['onOffState']:
                        newstate = updated_device.states["onOffState"]
                        currentstate = 1 if newstate == True else 0
                        if self.debug2:
                            self.logger.debug(f"{updateddevice_subtype} Subtype NewState of Device:{updated_device.name} & State: {newstate} & new State {currentstate}")
                        self.device_list_internal[checkindex]["accessory"].set_valve_state(currentstate)
                        return
                # Check Doorbell prior to Camera..
                elif str(updateddevice_subtype) == "Linked-DoorBell":
                    # if type(original_device) == indigo.RelayDevice:
                    if "onOffState" in updated_device.states:  ## double check Linked Doorbell are set only to have onOffStates
                        if updated_device.states['onOffState'] != original_device.states['onOffState']:
                            newstate = updated_device.onState
                            if self.debug2:
                                self.logger.debug("OnOffState Changed...and New State {}".format(newstate))
                            if self.debug2:
                                self.logger.debug("OnOffState of Device:{} & State: {} ".format(updated_device.name, newstate))
                            if newstate:  ##
                                self.device_list_internal[checkindex]["accessory"]._char_doorbell_detected.set_value(0)
                                self.device_list_internal[checkindex]["accessory"]._char_doorbell_detected_switch.set_value(0)
                    # if Doorbell nothing further to do... return regardless
                    return

                elif str(updateddevice_subtype) == "BlueIrisCamera":
                    # if type(original_device) == indigo.RelayDevice:
                    if updated_device.states['Motion'] != original_device.states['Motion']:
                        newstate = updated_device.states["Motion"]
                        if self.debug2:
                            self.logger.debug("Motion Changed...and New State {}".format(newstate))
                        if self.debug2:
                            self.logger.debug("NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        self.device_list_internal[checkindex]["accessory"].char_motion_detected.set_value(newstate)
                        return

                elif str(updateddevice_subtype) == "Fan":
                    ## Fan device has a brightnessLevel below, likely dimmer update Rotation speed with that.
                    ## Onoff will be active at bottom as well
                    if "brightnessLevel" in updated_device.states:
                        if updated_device.states['brightnessLevel'] != original_device.states['brightnessLevel']:
                            brightness = updated_device.states["brightnessLevel"]
                            if self.debug2:
                                self.logger.debug("This is a Fan: But found a brightnessLevel state try using that:  ValuetoSet: {}".format(brightness))
                            if isinstance(brightness, int):
                                self.device_list_internal[checkindex]["accessory"].char_rotation_speed.set_value(brightness)
                    elif type(updated_device) == indigo.SpeedControlDevice:
                        ## Speed control device update speedLevel hope rest follows... hard to test
                        ## strange device, hard to test
                        ## update speed index to that set by Homekit 0-100 fits
                        if updated_device.speedLevel != original_device.speedLevel:
                            speedLevel = updated_device.speedLevel
                            if self.debug2:
                                self.logger.debug("This is a Fan (HK) & SpeedControlDevice (indigo) found a speedLevel state try using that:  speedLevel: {}".format(speedLevel))
                            if isinstance(speedLevel, int):
                                self.device_list_internal[checkindex]["accessory"].char_rotation_speed.set_value(speedLevel)

                elif str(updateddevice_subtype) in ("Blind", "Window"):
                    if "brightnessLevel" in updated_device.states:
                        if updated_device.states['brightnessLevel'] != original_device.states['brightnessLevel']:
                            brightness = updated_device.states["brightnessLevel"]
                            if self.debug2:
                                self.logger.debug("Blind/Window: Found a brightnessLevel state try using that:  ValuetoSet: {}".format(brightness))
                            if isinstance(brightness, int):
                                self.device_list_internal[checkindex]["accessory"].set_covering_state(brightness, None)
                    elif "onOffState" in updated_device.states:
                        ## use brightness and calculate onOff first, if no brightness because of device - use on off and 100/0
                        ## Inverse can be actioned at the accessory level
                        if updated_device.states['onOffState'] != original_device.states['onOffState']:
                            newstate = updated_device.states["onOffState"]
                            if self.debug2:
                                self.logger.debug("Blind/Window: Defaulting to onOffState Check: NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                            self.device_list_internal[checkindex]["accessory"].set_covering_state(None, updated_device.states["onOffState"])

                if str(updateddevice_subtype) in ("HueLightBulb", "LightBulb", "ColorTempLightBulb"):
                    if "brightnessLevel" in updated_device.states:
                        if updated_device.states['brightnessLevel'] != original_device.states['brightnessLevel']:
                            brightness = updated_device.states["brightnessLevel"]
                            if self.debug2:
                                self.logger.debug("Found a brightnessLevel state try using that:  ValuetoSet: {}".format(brightness))
                            if isinstance(brightness, int):
                                self.device_list_internal[checkindex]["accessory"].Brightness.set_value(brightness)
                                self.device_list_internal[checkindex]["accessory"].HomeKitBrightnessLevel = brightness

                if str(updateddevice_subtype) in ( "HueLightBulb", "ColorTempLightBulb"):
                    # remove specific hue stuff, huelevel wrong and better to go one lower to indigo dimmer
                    if 'redLevel' in updated_device.states:  # and 'hue' not in updated_device.states:  ### if Hue - set with hue as above, if no hue use RGB here...  done- could move to RGB for all given HueLights...
                        ##   use redLevel as check for all if has redLevel, will have greenLevel & blueLevel no need to check for all
                        if updated_device.supportsRGB:  # has to otherwise wouldnt be huelightbulb - except for User Forcing - keep check
                            if updated_device.states['redLevel'] != original_device.states["redLevel"] or updated_device.states['blueLevel'] != original_device.states["blueLevel"] or updated_device.states['greenLevel'] != original_device.states["greenLevel"]:
                                ## check any updated, don't worry about state/brighgtess other changes
                                red = updated_device.states['redLevel']
                                green = updated_device.states['greenLevel']
                                blue = updated_device.states['blueLevel']
                                hsvReturned = colorsys.rgb_to_hsv(red / 100, green / 100, blue / 100)
                                # rgbReturned = colorsys.hsv_to_rgb(huetoSet / 360.0, saturationtoSet / 100.0, 1)
                                if self.debug2:
                                    self.logger.debug("Found updated Red/Green/Blue Level & Converted/Returned HSV data: {}".format(hsvReturned))
                                if len(hsvReturned) >= 1:
                                    self.device_list_internal[checkindex]["accessory"].Hue.set_value(hsvReturned[0] * 360)
                                    self.device_list_internal[checkindex]["accessory"].Saturation.set_value(hsvReturned[1] * 100)
                            elif "whiteTemperature" in updated_device.states:
                                if updated_device.supportsWhiteTemperature:
                                ## add check for whiteTemp supported - although won't be picked up by Hue...
                                    if updated_device.states["whiteTemperature"] != original_device.states["whiteTemperature"]:
                                        ## colortemp changed.
                                        mired = HKutils.color_temperature_kelvin_to_mired(updated_device.states["whiteTemperature"])
                                        if self.debug2:
                                            self.logger.debug("Found WhiteTemp Changed, converting to mired == {}".format(mired))
                                        hue, saturation = HKutils.color_temperature_to_hs(HKutils.color_temperature_mired_to_kelvin(mired))
                                        self.device_list_internal[checkindex]["accessory"].Hue.set_value(round(hue, 0))
                                        self.device_list_internal[checkindex]["accessory"].Saturation.set_value(round(saturation, 0))
                                        ## check for device state change in colorMode - below checks hue ?
                                        ## Not sure others - if not present will delay inteface update
                                        self.device_list_internal[checkindex]["accessory"].char_color_temp.set_value(round(mired, 0))
                            ## if huebulb and colorMode change notify
                            if "colorMode" in updated_device.states:
                                if updated_device.supportsWhiteTemperature and updated_device.supportsRGB:
                                    if updated_device.states["colorMode"] != original_device.states["colorMode"]:
                                        ## there has been a change in color mode
                                        ## should update
                                        if self.debug2:
                                            self.logger.debug("ColorMode has changed sending Notify to Hue,Sat, and ColorTemp.  New Mode {}".format(updated_device.states["colorMode"]))
                                        self.device_list_internal[checkindex]["accessory"].Hue.notify()
                                        self.device_list_internal[checkindex]["accessory"].Saturation.notify()
                                        self.device_list_internal[checkindex]["accessory"].char_color_temp.notify()

                if "onOffState" in updated_device.states and str(updateddevice_subtype) not in ("Blind", "Window"):   ## work around to remnove this TODO
                    if updated_device.states['onOffState'] != original_device.states['onOffState']:
                        newstate = updated_device.states["onOffState"]
                        if self.debug2:
                            self.logger.debug("onOffState Check: NewState of Device:{} & State: {} ".format(updated_device.name, newstate))
                        self.device_list_internal[checkindex]["accessory"].char_on.set_value(newstate)

        except:
            self.logger.debug("Caught exception in Device Update", exc_info=True)
        ## Motion Detected

    ## TODO consider move to Que model and thread setter out
    def Plugin_setter_callback(self, accessoryself, statetoReturn, valuetoSet):
        try:
            if self.debug5:
                self.logger.debug("Plugin Setter Callback Called")
                self.logger.debug("Indigo DeviceID {}".format(accessoryself.indigodeviceid))
                self.logger.debug("State Wished:" + str(statetoReturn))
                self.logger.debug(f"Char_Values {type(valuetoSet)} to Set: {valuetoSet}")
            stateList = []
            #   dev.updateStatesOnServer(stateList)
            indigodevice = self.return_deviceorAG(accessoryself.indigodeviceid)  # .devices[accessoryself.indigodeviceid]

            if type(indigodevice) == indigo.ActionGroup:
                if self.debug5:
                    self.logger.debug("Found action group - turning on")
                if "On" in valuetoSet:
                    if valuetoSet["On"] == 1:
                        indigo.actionGroup.execute(accessoryself.indigodeviceid)
                elif "Active" in valuetoSet:
                    if valuetoSet["Active"] == 1:
                        indigo.actionGroup.execute(accessoryself.indigodeviceid)
                return  ## nothing more to do here

            if statetoReturn == "Thermostat_state":
                unit = indigodevice.pluginProps.get("HomeKit_tempSelector", False)
                ## need device to see if Cool or Heat to know what Target is referring to
                # {'TargetTemperature': 22.5, 'CoolingThresholdTemperature': 24, 'HeatingThresholdTemperature': 21}
                # {'TargetTemperature': 21.5}
                '''
                Current
                     "Cool": 2,
                     "Heat": 1,
                     "Off": 0
                Target
                    "Auto": 3,
                    "Cool": 2,
                    "Heat": 1,
                    "Off": 0
                '''
                listHvacModes = {0: indigo.kHvacMode.Off,
                                 1: indigo.kHvacMode.Heat,
                                 2: indigo.kHvacMode.Cool,
                                 3: indigo.kHvacMode.HeatCool}

                if hasattr(indigodevice, "hvacMode"):
                    currentMode = indigodevice.hvacMode
                    if "TargetHeatingCoolingState" in valuetoSet:
                        ## Wants to change state of thermostat - do that first and then
                        modewished = valuetoSet["TargetHeatingCoolingState"]
                        indigomodewished = listHvacModes[modewished]
                        # 0 = off, 1- heat, 2 cool, 3 auto
                        if self.debug5:
                            self.logger.debug("CurrentMode: {}, and wised Mode:{} and indigo Mode: {} ".format(currentMode, modewished, indigomodewished))
                        modechange = False
                        if currentMode == indigo.kHvacMode.Off and modewished in (1, 2, 3):
                            indigo.thermostat.setHvacMode(accessoryself.indigodeviceid, value=indigomodewished)
                            modechange = True
                        elif currentMode == indigo.kHvacMode.Cool and modewished in (0, 1, 3):
                            indigo.thermostat.setHvacMode(accessoryself.indigodeviceid, value=indigomodewished)
                            modechange = True
                        elif currentMode == indigo.kHvacMode.Heat and modewished in (0, 2, 3):
                            indigo.thermostat.setHvacMode(accessoryself.indigodeviceid, value=indigomodewished)
                            modechange = True
                        elif currentMode == indigo.kHvacMode.HeatCool and modewished in (0, 1, 2):
                            indigo.thermostat.setHvacMode(accessoryself.indigodeviceid, value=indigomodewished)
                            modechange = True
                        ## call Thermostat device to update target and values
                        if modechange:
                            if self.debug5:
                                self.logger.debug("Thermostat Device has been changed, updating all temp targets/setpoints")
                            if 'setpointCool' in indigodevice.states:
                                setpointcool = indigodevice.states['setpointCool']
                                setpointheat = indigodevice.states['setpointHeat']
                                if indigomodewished == indigo.kHvacMode.Off:
                                    pass
                                elif indigomodewished == indigo.kHvacMode.Heat:
                                    ## set targettemp to setpointHeat
                                    accessoryself.set_temperature(HKutils.convert_to_float(setpointheat), "target")
                                elif indigomodewished == indigo.kHvacMode.Cool:
                                    ## set targettemp to setpointHeat
                                    accessoryself.set_temperature(HKutils.convert_to_float(setpointcool), "target")
                                elif indigomodewished == indigo.kHvacMode.HeatCool:
                                    ## set targettemp to setpointHeat
                                    accessoryself.set_temperature(HKutils.convert_to_float(setpointcool), "coolthresh")
                                    accessoryself.set_temperature(HKutils.convert_to_float(setpointheat), "heatthresh")

                    if "TargetTemperature" in valuetoSet:
                        target_temp = valuetoSet['TargetTemperature']
                        if unit:  ## if F select will need to convert
                            target_temp = HKutils.celsius_to_fahrenheit(target_temp)  ## Homekit always in Celsius so if using F convert back. for Indigo.
                            if self.debug5:
                                self.logger.debug("TargetTemperature found and converted to {}".format(target_temp))
                        if currentMode == indigo.kHvacMode.Off:
                            ## ignore everything?
                            pass
                        elif currentMode == indigo.kHvacMode.Cool:
                            if self.debug5:
                                self.logger.debug("Mode kHvac Cool setting CoolSetpoint to {}".format(target_temp))
                            indigo.thermostat.setCoolSetpoint(accessoryself.indigodeviceid, value=target_temp)
                        elif currentMode == indigo.kHvacMode.Heat:
                            if self.debug5:
                                self.logger.debug("Mode kHvac Cool setting HeatSetPoint to {}".format(target_temp))
                            indigo.thermostat.setHeatSetpoint(accessoryself.indigodeviceid, value=target_temp)
                        elif currentMode == indigo.kHvacMode.HeatCool:
                            if "CoolingThresholdTemperature" in valuetoSet:
                                cooltarget = valuetoSet["CoolingThresholdTemperature"]
                                if unit:  ## if F select will need to convert
                                    cooltarget = HKutils.celsius_to_fahrenheit(cooltarget)
                                if self.debug5:
                                    self.logger.debug("Mode kHvac Auto, using CoolingThreshold Temp and setting CoolSetpoint to {}".format(cooltarget))
                                indigo.thermostat.setCoolSetpoint(accessoryself.indigodeviceid, value=cooltarget)
                            if "HeatingThresholdTemperature" in valuetoSet:
                                heattarget = valuetoSet["HeatingThresholdTemperature"]
                                if unit:  ## if F select will need to convert
                                    heattarget = HKutils.celsius_to_fahrenheit(heattarget)
                                if self.debug5:
                                    self.logger.debug("Mode kHvac Auto, using HeatingThreshold Temp and setting HeatPoint to {}".format(cooltarget))
                                indigo.thermostat.setHeatSetpoint(accessoryself.indigodeviceid, value=heattarget)

            elif statetoReturn == "lockState":
                if "onOffState" in indigodevice.states:
                    if indigodevice.onState:
                        ## Device On
                        if isinstance(valuetoSet, list):  # device already On
                            if "LockTargetState" in valuetoSet:
                                if valuetoSet["LockTargetState"] == 1:
                                    if self.debug5:
                                        self.logger.debug("Setter.  Lockstate. List : Device already Locked.  But regardless given lock - I will resend. ")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                                    accessoryself.char_target_state.set_value(1)
                                    #accessoryself.char_current_state.set_value(1)
                                else:  # TargetLockState exisits here
                                    if self.debug5:
                                        self.logger.debug("Device On and wishes to be Unlocked turning Off.")
                                    indigo.device.turnOff(accessoryself.indigodeviceid)
                                    accessoryself.char_target_state.set_value(0)
                                    #accessoryself.char_current_state.set_value(1)
                        elif isinstance(valuetoSet, int):
                            if valuetoSet == 1:
                                if self.debug5:
                                    self.logger.debug("Settter.  Lockstate: Int Device already Locked. But Given Lock will send command.")
                                indigo.device.turnOn(accessoryself.indigodeviceid)
                                accessoryself.char_target_state.set_value(1)  #
                                #accessoryself.char_current_state.set_value(1)
                            else:  # ==0 presumably exisits here
                                if self.debug5:
                                    self.logger.debug("Device On and wishes to be Unlocked turning Off.")
                                indigo.device.turnOff(accessoryself.indigodeviceid)
                    else:  ## Indigo Device Off Reverse - should function this.
                        ## Indigo Device is OFF
                        if isinstance(valuetoSet, list):
                            if "LockTargetState" in valuetoSet:
                                if valuetoSet["LockTargetState"] == 1:
                                    if self.debug5:
                                        self.logger.debug("Device command to Lock")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                                else:
                                    if self.debug5:
                                        self.logger.debug("Device Unlocked and wishes to be Unlocked. Repeating.")
                                    indigo.device.turnOff(accessoryself.indigodeviceid)
                                    accessoryself.char_target_state.set_value(0)
                            else:
                                if self.debug5:
                                    self.logger.debug(f"No LockTargetState found skipping.  vaLuetoSet: {valuetoSet}")
                        elif isinstance(valuetoSet, int):
                            ## 1 or 0 just set
                            if valuetoSet == 1:
                                if self.debug5:
                                    self.logger.debug("Setter. Lockstate. Int. Device Unlocked, command to Lock")
                                indigo.device.turnOn(accessoryself.indigodeviceid)
                                accessoryself.char_target_state.set_value(1)
                                #accessoryself.char_current_state.set_value(1)
                            else:
                                if self.debug5:
                                    self.logger.debug("Device Unlocked and wishes to be Unlocked. Repeating")
                                indigo.device.turnOff(accessoryself.indigodeviceid)
                                accessoryself.char_target_state.set_value(0)
                else:
                    if self.debug5:
                        self.logger.debug("No onOffState within Lock.. Not sure what to set.  Ending.")

            elif statetoReturn == 'valveState':
                if "onOffState" in indigodevice.states:
                    if self.debug5:
                        self.logger.debug("Found onOffState using that..")
                    if indigodevice.onState:  # device already On
                        if "Active" in valuetoSet:
                            if valuetoSet["Active"] == 1:
                                if self.debug5:
                                    self.logger.debug("Device already On.  Turning On regardless.")
                                indigo.device.turnOn(accessoryself.indigodeviceid)

                            elif valuetoSet["Active"] == 0:
                                if self.debug5:
                                    self.logger.debug("Device On and wishes to be Off turning Off.")
                                indigo.device.turnOff(accessoryself.indigodeviceid)

                        else:
                            if self.debug5:
                                self.logger.debug("No On or Active found in valuetoSet.. ending here.")
                    else:  ## device off
                        if "Active" in valuetoSet:
                            if valuetoSet["Active"] == 1:
                                if self.debug5:
                                    self.logger.debug("Device Off.  Wishing to be On.  Turning On regardless.")
                                indigo.device.turnOn(accessoryself.indigodeviceid)

                            elif valuetoSet["Active"] == 0:
                                if self.debug5:
                                    self.logger.debug("Device Off and wishes to be On turning On.")
                                indigo.device.turnOff(accessoryself.indigodeviceid)

                        else:
                            if self.debug5:
                                self.logger.debug("No On or Active found in valuetoSet.. ending here.")
                return

            if statetoReturn == "onOffState":
                # variable to share across HK devices - justturnedon
                brightnessSet = False
                # attempt to get onOffState
                if "Brightness" in valuetoSet:  ## change brightness then turn on other full bright them dim
                    ## got a on/off and a Brightness together yah - we can sort that out
                    if "brightnessLevel" in indigodevice.states:
                        if self.debug5:
                            self.logger.debug("Found a brightnessLevel state in IndigoDevice try using that:  ValuetoSet: {}".format(valuetoSet))
                        currentBrightness = indigodevice.states["brightnessLevel"]

                        if valuetoSet["Brightness"] != currentBrightness:
                            if self.debug5:
                                self.logger.debug("Brightness level differs changing..")
                            if isinstance(valuetoSet["Brightness"], int):
                                indigo.dimmer.setBrightness(accessoryself.indigodeviceid, int(valuetoSet["Brightness"]))
                                if valuetoSet["Brightness"] > 0:
                                    brightnessSet = True
                        else:  # even if not equal don't TURN ON below
                            brightnessSet = True
                if "RotationSpeed" in valuetoSet:  ## fan action, fan also uses active as below
                    if type(indigodevice) == indigo.SpeedControlDevice:
                        ## strange device, hard to test
                        ## update speed index to that set by Homekit 0-100 fits
                        if isinstance(valuetoSet["RotationSpeed"], int):
                            indigo.speedcontrol.setSpeedLevel(indigodevice.id, value=int(valuetoSet["RotationSpeed"]))
                            if int(valuetoSet["RotationSpeed"]) > 0:
                                brightnessSet = True  ## Fan speed changed so don't turn on off as well!
                    # $ else below - if not speed Control device, most likely dimmer and brightness level to = RotationSpeed
                    elif "brightnessLevel" in indigodevice.states:
                        if self.debug5:
                            self.logger.debug("Found a brightnessLevel state in IndigoDevice try using that:  ValuetoSet: {}".format(valuetoSet))
                        currentBrightness = indigodevice.states["brightnessLevel"]
                        if valuetoSet["RotationSpeed"] != currentBrightness:
                            if self.debug5:
                                self.logger.debug("RotationSpeed and brightness level differs changing..")
                            if isinstance(valuetoSet["RotationSpeed"], int):
                                indigo.dimmer.setBrightness(accessoryself.indigodeviceid, int(valuetoSet["RotationSpeed"]))
                                if valuetoSet["RotationSpeed"] > 0:
                                    brightnessSet = True  ## Fan speed changed so don't turn on off as well!
                ## still go to below if needed.
                if "onOffState" in indigodevice.states:
                    if self.debug5:
                        self.logger.debug("Found onOffState using that..")
                    if indigodevice.onState:  # device already On
                        if "On" in valuetoSet:
                            if valuetoSet["On"] == 1:
                                if brightnessSet == False:
                                    if self.debug5:
                                        self.logger.debug("Device already On.  Turning On regardless.")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                            elif valuetoSet["On"] == 0:
                                if self.debug5:
                                    self.logger.debug("Device On and wishes to be Off turning Off.")
                                indigo.device.turnOff(accessoryself.indigodeviceid)
                        elif "Active" in valuetoSet:
                            if valuetoSet["Active"] == 1:
                                if brightnessSet == False:
                                    if self.debug5:
                                        self.logger.debug("Device already On.  Turning On regardless.")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                            elif valuetoSet["Active"] == 0:
                                if self.debug5:
                                    self.logger.debug("Device On and wishes to be Off turning Off.")
                                indigo.device.turnOff(accessoryself.indigodeviceid)
                        else:
                            if self.debug5:
                                self.logger.debug("No On or Active found in valuetoSet.. ending here.")
                    else:  ## Indigo Device Off Reverse - should function this.
                        ## Indigo Device is OFF
                        if "On" in valuetoSet:
                            if valuetoSet["On"] == 1:
                                if brightnessSet == False:  ## Negative logic so those no brightness devices still turnOn
                                    ## If I have just set Brightness to greater than 0 don't turn on as that setts brightness to 100%
                                    if self.debug5:
                                        self.logger.debug("Device Off, command to turn on")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                            else:
                                if self.debug5:
                                    self.logger.debug("Device Off and wishes to be Off. Repeat")
                                indigo.device.turnOff(accessoryself.indigodeviceid)
                        elif "Active" in valuetoSet:
                            if valuetoSet["Active"] == 1:
                                if brightnessSet == False:  ## Negative logic so those no brightness devices still turnOn
                                    ## If I have just set Brightness to greater than 0 don't turn on as that setts brightness to 100%
                                    if self.debug5:
                                        self.logger.debug("Device Off, command to turn on")
                                    indigo.device.turnOn(accessoryself.indigodeviceid)
                            else:
                                if self.debug5:
                                    self.logger.debug("Device Off and wishes to be Off. Repeat")
                                indigo.device.turnOff(accessoryself.indigodeviceid)

                else:  ## Button switchs action groups etc
                    ## asked to return onOffState but doesn't exist in IndigoDevice states
                    ## if device just turn off/on and see
                    ## if AG just run
                    if type(indigodevice) == indigo.ActionGroup:
                        if self.debug5:
                            self.logger.debug("Found action group - turning on")
                        if "On" in valuetoSet:
                            if valuetoSet["On"] == 1:
                                indigo.actionGroup.execute(accessoryself.indigodeviceid)
                    elif type(indigodevice) == indigo.MultiIODevice:
                        ## Insteon likely Garage Door device
                        ## How are we getter value
                        if "On" in valuetoSet:
                            if valuetoSet["On"] == 1:  ## This runs when garage door is open, i.e. binaryInput1 = off
                                if self.debug5:
                                    self.logger.debug("I/O Device valuetoSet is 1")
                                indigo.iodevice.setBinaryOutput(accessoryself.indigodeviceid, index=0, value=True)
                            elif valuetoSet["On"] == 0:  ## This runs when garage door is closed, i.e. binaryInput1 = on
                                if self.debug5:
                                    self.logger.debug("I/O Device valuetoSet is 0")
                                indigo.iodevice.setBinaryOutput(accessoryself.indigodeviceid, index=0, value=True)
                    else:
                        if "On" in valuetoSet:
                            if valuetoSet["On"] == 1:
                                indigo.device.turnOn(accessoryself.indigodeviceid)
                            elif valuetoSet["On"] == 0:  ## As currently stands this should never run as devices lacking onOffStates are recorded as activate only
                                indigo.device.turnOff(accessoryself.indigodeviceid)

            elif statetoReturn == "Hue":
                if indigodevice.supportsRGB:
                    if self.debug5:
                        self.logger.debug("Found a Hue state try using that (also using Sat)..")
                    if "Hue" in valuetoSet:
                        huetoSet = valuetoSet["Hue"]
                        ## seems that if Hue always Saturdation.... not if 100%
                        if "Saturation" in valuetoSet:
                            saturationtoSet = valuetoSet["Saturation"]
                        else:
                            saturationtoSet = 100
                    rgbReturned = colorsys.hsv_to_rgb(huetoSet / 360.0, saturationtoSet / 100.0, 1)
                    #  rgbReturned = colorsys.hls_to_rgb(huetoSet/360,1, saturationtoSet/100)
                    if self.debug5:
                        self.logger.debug("Returned RGB data: {}".format(rgbReturned))
                        self.logger.debug("RGB:{}".format(rgbReturned))
                    if len(rgbReturned) >= 2:
                        if indigodevice.pluginId == "com.nathansheldon.indigoplugin.HueLights":
                            ## Change approach as don't like impact elsewhere.  Select for Hue ssues
                            ## When Hue plugin changes Hue of lights - sets Brightness to maximal value or RG or B
                            ## see here: https://forums.indigodomo.com/viewtopic.php?t=24035&p=196064
                            ## Hence everytime HomeKit requests a Hue change alone - brightness becomes annoyingly 100%
                            if "Brightness" in valuetoSet:
                                deviceBrightness = int(valuetoSet["Brightness"])
                            else:
                                #deviceBrightness = indigodevice.states["brightnessLevel"]
                                deviceBrightness = accessoryself.HomeKitBrightnessLevel
                            indigo.dimmer.setColorLevels(accessoryself.indigodeviceid, rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100 )
                            if self.debug5:
                                self.logger.debug("HueDeviceFound: Set Color Levels of Device to R:{}  G:{}  B:{}.   Current Device Brightness:{} ".format(rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100, deviceBrightness))
                            if isinstance(deviceBrightness, int):
                                indigo.dimmer.setBrightness(accessoryself.indigodeviceid, deviceBrightness)
                                if self.debug5:
                                    self.logger.debug("HueDeviceFound: Additional Brightness Setting. Set Brightness Seperately to  Brightness:{} ".format( deviceBrightness))
                            else:  # do same in case of Hue Error/no Brightness given
                                indigo.dimmer.setColorLevels(accessoryself.indigodeviceid, rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100)
                                if self.debug5:
                                    self.logger.debug("HueDeviceFound: Missing Details, Basic. Set Color Levels of Device to R:{}  G:{}  B:{}".format(rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100))
                        else:
                            indigo.dimmer.setColorLevels(accessoryself.indigodeviceid, rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100)
                            if self.debug5:
                                self.logger.debug("Set Color Levels of Device to R:{}  G:{}  B:{}".format(rgbReturned[0] * 100, rgbReturned[1] * 100, rgbReturned[2] * 100))

            elif statetoReturn == "ColorTemperature":  ## state and value named the same here..
                if self.debug5:
                    self.logger.debug("Found a ColorTemperature state try using that..")
                    # convert to kelvin
                if indigodevice.supportsWhiteTemperature:
                    kelvin = HKutils.color_temperature_mired_to_kelvin(valuetoSet["ColorTemperature"])
                    if self.debug5:
                        self.logger.debug("Setting to Temp {} Kelvin ".format(kelvin))
                    indigo.dimmer.setColorLevels(accessoryself.indigodeviceid, whiteTemperature=kelvin)
            elif statetoReturn == "Saturation":
                if "saturation" in indigodevice.states:
                    if self.debug5:
                        self.logger.debug("Found a Saturation state ignoring that..")


        except:
            self.logger.exception("Error in setter callback")

    def Plugin_getter_callback(self, accessoryself, statetoGet):

        try:

            if self.debug4:
                self.logger.debug("Plugin getter Called: Indigo DeviceID {} State {} ".format(accessoryself.indigodeviceid, statetoGet))

            indigodevice = indigo.devices[accessoryself.indigodeviceid]

            if statetoGet in ("temperature", "SensorLeak", "humidity", "LightLevel", "sensorOccupancy", "sensorSmoke", "SensorCarbonDioxide", "SensorCarbonMonoxide", "sensorContactSensor"):  ## this could actually be a number of options..
                ## attempt to get temperature
                ## Use the saved device to figure out what State to return..
                ## now where is that saved device info gone...
                ## should remain in internal device list, iter that and pull the Sensor state using...
                ## Can use this for every sensor -- will need to check for correct values otherwise HK == crash
                checkindex = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == indigodevice.id), None)
                if checkindex != None:
                    sensortouse = self.device_list_internal[checkindex]["devicesensor"]
                else:
                    self.logger.debug("Plugin getter Called: Indigo DeviceID {} State {} ".format(accessoryself.indigodeviceid, statetoGet))
                    return
                ## First check if sensor device and then easy - use sensorValue
                if type(indigodevice) == indigo.SensorDevice:
                    ## should default to selected state
                    if sensortouse != "sensorValue":
                        if sensortouse in indigodevice.states:
                            sensorvalue = HKutils.convert_to_float(indigodevice.states[sensortouse])
                            if type(sensorvalue) in (float, int):
                                if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                    sensorvalue = 100000
                            if self.debug4:
                                self.logger.debug("Device {} + SensorValue:{} + type(sensorValue) {}".format(indigodevice.name, sensorvalue, type(sensorvalue)))
                            return sensorvalue  # indigodevice.states[sensortouse]
                    else:
                        if "sensorValue" in indigodevice.states:
                            if self.debug4:
                                self.logger.debug("Found a Sensor value, using that")
                            sensorvalue = indigodevice.states["sensorValue"]
                            if type(sensorvalue) in (float, int):
                                if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                    sensorvalue = 100000  ## true / false results thought... should never be greater but will be less than... should be okay
                            return sensorvalue
                ## else check internal list for sensor State that we wish to return back
                else:  ## if another device use the selectred state
                    if sensortouse != "":
                        if sensortouse in indigodevice.states:
                            sensorvalue = indigodevice.states[sensortouse]
                            if type(sensorvalue) in (float, int):
                                if sensorvalue > 100000:  ## should be hit by LightSensor or really really hot days...
                                    sensorvalue = 100000
                            if self.debug4:
                                self.logger.debug("Device {} + SensorValue:{} + type(sensorValue) {}".format(indigodevice.name, sensorvalue, type(sensorvalue)))
                            return sensorvalue  # indigodevice.states[sensortouse]

            elif statetoGet == "onOffState":
                # attempt to get onOffState
                if "onOffState" in indigodevice.states:
                    if self.debug4:
                        self.logger.debug("Found onOffState using that..")
                    return indigodevice.states["onOffState"]

            elif statetoGet == "windowCovering":
                if "brightnessLevel" in indigodevice.states:
                    if self.debug4:
                        self.logger.debug("Found a brightnessLevel state try using that, for WindowCovering..")
                    return indigodevice.states["brightnessLevel"],None
                elif "onOffState" in indigodevice.states:
                    newstate = indigodevice.states["onOffState"]
                    if self.debug4:
                        self.logger.debug("Blind: Defaulting to onOffState using onOffState {} ".format(newstate))
                    return None,newstate

            elif statetoGet == "windowAlone":
                if "brightnessLevel" in indigodevice.states:
                    if self.debug4:
                        self.logger.debug("Window: Found a brightnessLevel state try using that, for WindowCovering..")
                    return indigodevice.states["brightnessLevel"],None
                elif "onOffState" in indigodevice.states:
                    newstate = indigodevice.states["onOffState"]
                    if self.debug4:
                        self.logger.debug("Window: Defaulting to onOffState using onOffState {} ".format(newstate))
                    return None,newstate

            elif statetoGet == "garageDoorState":
                for stateName in ("doorState", "onOffState", "binaryInput1"):  # ordered by preference
                    if stateName in indigodevice.states:  # choose the first match
                        if self.debug4:
                            self.logger.debug("Found {} using that..".format(stateName))
                        return indigodevice.states[stateName]

            elif statetoGet == "lockState":
                if "onOffState" in indigodevice.states:
                    if self.debug4:
                        self.logger.debug("lockState: Found onOffState using that..")
                    return indigodevice.states["onOffState"]

            elif statetoGet == "Hue":
                # hue often wrong in HueLights and better to go basic and down to diimmer class anyway..
                # if "hue" in indigodevice.states:

                #     if self.debug4:
                #         self.logger.debug("Found a Hue state try using that..")
                #     return indigodevice.states["hue"]
                if "redLevel" in indigodevice.states:
                    ## calculate the Hue
                    red = indigodevice.states['redLevel']
                    green = indigodevice.states['greenLevel']
                    blue = indigodevice.states['blueLevel']
                    hsvReturned = colorsys.rgb_to_hsv(red / 100, green / 100, blue / 100)
                    if self.debug4:
                        self.logger.debug("Calculated HSV data: {}".format(hsvReturned))
                    if len(hsvReturned) >= 1:
                        return hsvReturned[0] * 360

            elif statetoGet == "Saturation":
                # if "saturation" in indigodevice.states:
                #     if self.debug4:
                #         self.logger.debug("Found a Saturation state try using that..")
                #     return indigodevice.states["saturation"]
                if "redLevel" in indigodevice.states:
                    ## calculate the Hue
                    red = indigodevice.states['redLevel']
                    green = indigodevice.states['greenLevel']
                    blue = indigodevice.states['blueLevel']
                    hsvReturned = colorsys.rgb_to_hsv(red / 100, green / 100, blue / 100)
                    if self.debug4:
                        self.logger.debug("Calculated HSV data: {}".format(hsvReturned))
                    if len(hsvReturned) >= 1:
                        return hsvReturned[1] * 100  ## = saturdation

            elif statetoGet == "Brightness":
                if "brightnessLevel" in indigodevice.states:
                    if self.debug4:
                        self.logger.debug("Found a brightnessLevel state try using that..")
                    return indigodevice.states["brightnessLevel"]

            elif statetoGet == "Thermostat_temp":
                if hasattr(indigodevice, "temperatures"):
                    if self.debug4:
                        self.logger.debug(f"Checking Thermostat temp (found temperatures) against device: {indigodevice.name}")  ## double check here in
                    listtemps = indigodevice.temperatures
                    if self.debug4:
                        self.logger.debug(f"Checking Thermostat temp List temperatures: {listtemps}")  ## double check here in
                    if isinstance(listtemps, list):
                        if not listtemps:  ## Check for empty List, Len(listtemps)=0, DivisionZero in that case
                            return 0  ## return 0 or None.  Getter changes None to 0?
                        else:
                            temptosend = sum(listtemps) / len(listtemps)  ##avreturn 0
                    elif isinstance(listtemps, (float, int)):
                        temptosend = listtemps
                    else:
                        temptosend = 1.3
                    if self.debug4:
                        self.logger.debug("Updating Temperature to {}".format(temptosend))
                    return temptosend

            elif statetoGet == "Thermostat_target_temp":
                if "hvacOperationModeIsAuto" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsAuto"]:
                        if self.debug4:
                            self.logger.debug("hvacOperationMode Auto Thermostat.")
                        temp1 = indigodevice.states['setpointCool']
                        temp2 = indigodevice.states['setpointHeat']
                        temptosend = (HKutils.convert_to_float(temp1)+HKutils.convert_to_float(temp2)) / 2
                        if self.debug4:
                            self.logger.debug("Updating Mode Auto: Target Temperature to {}".format(temptosend))
                        return temptosend
                    if indigodevice.displayStateImageSel == indigo.kStateImageSel.HvacCoolMode or indigodevice.displayStateImageSel == indigo.kStateImageSel.HvacCooling:
                        # setpointCool
                        if 'setpointCool' in indigodevice.states:
                            temptosend = indigodevice.states['setpointCool']
                            return temptosend
                    elif indigodevice.displayStateImageSel == indigo.kStateImageSel.HvacHeatMode or indigodevice.displayStateImageSel == indigo.kStateImageSel.HvacHeating:
                        if 'setpointHeat' in indigodevice.states:
                            temptosend = indigodevice.states['setpointHeat']
                            return temptosend

                    #return temptosend

            elif statetoGet in ("Thermostat_targetState",):
                if "hvacOperationModeIsAuto" in indigodevice.states:
                    if statetoGet == "Thermostat_targetState":
                        if indigodevice.states["hvacOperationModeIsAuto"]:
                            if self.debug4:
                                self.logger.debug("hvacOperationMode Auto Thermostat.  Returning 3")
                            return 3  ## 3 = Auto
                if "hvacOperationModeIsCool" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsCool"]:
                        if self.debug4:
                            self.logger.debug("hvacOperationMode Cool Thermostat.  Returning 2")
                        return 2  ## 3 = Auto
                if "hvacOperationModeIsHeat" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsHeat"]:
                        if self.debug4:
                            self.logger.debug("hvacOperationMode Heat.  Returning 1")
                        return 1  ## 3 = Auto
                if "hvacOperationModeIsOff" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsOff"]:
                        if self.debug4:
                            self.logger.debug("hvacOperationMode OFF Thermostat.  Returning 0")
                        return 0  ## 3 = Auto

            elif statetoGet in ("Thermostat_currentState"):
                if "hvacOperationModeIsOff" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsOff"]:
                        if self.debug4:
                            self.logger.debug(f"Getter: hvacMode == Off, returning 0")
                        return 0
                if "hvacOperationModeIsAuto" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsAuto"]:
                        if self.debug4:
                            self.logger.debug("Getter: hvacOperationMode Auto Thermostat.  Checking Fans")
                        if "hvacCoolerIsOn" in indigodevice.states:
                            if indigodevice.states["hvacCoolerIsOn"] == True:
                                return 2
                        if "hvacHeaterIsOn" in indigodevice.states:
                            if indigodevice.states["hvacHeaterIsOn"] == True:
                                return 1 # cooling
                            else:
                                return 0 # idle
                if "hvacOperationModeIsHeat" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsHeat"]:
                        if self.debug4:
                            self.logger.debug(f"Getter: hvacMode == Heat and current Heater is {indigodevice.states['hvacHeaterIsOn']}")
                        if 'hvacHeaterIsOn' in indigodevice.states:
                            if indigodevice.states["hvacHeaterIsOn"] == False:
                                return 0
                            else:
                                return 1
                        else:
                            return 0
                if "hvacOperationModeIsCool" in indigodevice.states:
                    if indigodevice.states["hvacOperationModeIsCool"]:
                        if self.debug4:
                            self.logger.debug(f"Getter: hvacMode == Cool and current Cooler is {indigodevice.states['hvacCoolerIsOn']}")
                        if 'hvacCoolerIsOn' in indigodevice.states:
                            if indigodevice.states["hvacCoolerIsOn"] == False:
                                return 0
                            else:
                                return 2
                        else:
                            return 0

        except:
            self.logger.exception("Plugin Setter Exception")


        ## aim of this routine is to be run once with creation of the HomeKit Bridge
        ## sending back the accessory details to be stored in Dict of HomeKit devices
        ## This then can be called back to accessory

    def Plugin_addCallbacktoDeviceList(self, accessoryself):
        try:
            if self.debug4:
                self.logger.debug("Inital at Start: Setting up Accessory {}".format(accessoryself.indigodeviceid))

            check = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == accessoryself.indigodeviceid), None)
            # check=  next((item for item in self.device_list_internalif item["deviceid"] == ), False)
            if check != None:
                # self.logger.info("Found Key= {}".format(check))
                self.device_list_internal[check]["accessory"] = accessoryself
                # below doesn't catch those without callback == temp sensors - but they still need callback...
                self.runningAccessoryCount = self.runningAccessoryCount + 1
                ## if checking and camera, add callback if DoorBell Accessory exists to same accessory as Camera...
                self.logger.debug("{}".format(accessoryself.services))
                check_doorbell = None
                for service in accessoryself.services:
                    # self.logger.error("{}".format(service.display_name))
                    if str(service.display_name) == "Doorbell":
                        check_doorbell = True
                        self.logger.debug("Found Doorbell:{}".format(service))
                if check_doorbell != None:
                    ## is DoorBell and potentially other Special == linked devices
                    self.logger.debug("Found Doorbell Service {}".format(accessoryself))
                    if accessoryself.doorbellID != None:
                        self.logger.debug("Found DoorBell ID in Accessory. = {} \nSearching self.device_list_internal for it..".format(accessoryself.doorbellID))
                        doorbell_ID_Found = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == int(accessoryself.doorbellID)), None)
                        if doorbell_ID_Found != None:
                            self.logger.debug("Check DoorBell Found: {}".format(doorbell_ID_Found))
                            self.device_list_internal[doorbell_ID_Found]["accessory"] = accessoryself

                if self.debug4:
                    self.logger.debug("{}".format(accessoryself))
        except:
            self.logger.exception("Error.")

    def check_activateOnly(self, deviceid):  # called by HKDevice to check nature of swtich
        if self.debug4:
            self.logger.debug("checking whether activate only nature of switch")
        indigodevice = self.return_deviceorAG(deviceid)  # indigo.devices[deviceid]
        if type(indigodevice) == indigo.ActionGroup:
            return True
        if "onOffState" in indigodevice.states:
            return False
        if indigodevice.model == "I/O-Linc Controller":
            return False
        else:
            return True

    # def manage_event(self, accessoryself):
    #     # self.logger.info("Manged Event Called")
    #     # self.logger.info("{}".format(accessoryself))
    #
    #     indigodevice = indigo.devices[accessoryself.indigodeviceid]
    #     # self.logger.info(indigodevice.states )
    #     if accessoryself.char_motion != None:
    #         if indigodevice.states["onOffState"]:
    #             # self.logger.info("Char_Motion Set Value True")
    #             accessoryself.char_motion.set_value(True)
    #         else:
    #             accessoryself.char_motion.set_value(False)
    #     # else:
    #     # accessoryself.char_temp.set_value(random.randint(18, 26))

    def validatePrefsConfigUi(self, valuesDict):

        self.debugLog(u"validatePrefsConfigUi() method called.")
        error_msg_dict = indigo.Dict()
        return (True, valuesDict)

        ## Generate QR COde for Homekit and open Web-Browser to display - is a PNG

    def showQRcode(self, values_dict, type_id="", dev_id=None):
        # self.logger.debug("{} & dev_id {}".format(values_dict,dev_id))
        device = self.return_deviceorAG(int(dev_id))  ## device or AG
        if device == None:
            self.logger.error("Error Saving this device.")
            return
        self.logger.debug("Show QR Code.  Saving Http page.")
        try:
            if device.states["QRCode"] != None:
                QRhttp = open("QRCode.html", "w")
                Qrcodedata = device.states["QRCode"]  ## I know - could be plugin prefs but here it is
                Qrcodedata = Qrcodedata.replace("<div><h1>HomeKitLink Siri</h1>", "<div><h1>  HomeKitLink Siri</h1>\n<h1> Device: " + str(device.name) + "</h1>\n")
                Qrcodedata = '''<head><link rel="shortcut icon" href="https://static.indigodomo.com/www/favicon.ico">
                    <link href="https://static.indigodomo.com/www/bootstrap/css/bootstrap.min.css" rel="stylesheet">
    <!-- HTML5 shim and Respond.js IE8 support of HTML5 elements and media queries -->
    <!--[if lt IE 9]>
      <script src="https://oss.maxcdn.com/libs/html5shiv/3.7.0/html5shiv.js"></script>
      <script src="https://oss.maxcdn.com/libs/respond.js/1.4.2/respond.min.js"></script>
    <![endif]-->

    <!-- Custom styles for this template -->
    <link href="https://static.indigodomo.com/www/css/indigodomo.css" rel="stylesheet">
    <link href="https://static.indigodomo.com/www/font-awesome/css/font-awesome.css" rel="stylesheet">
    <link href="https://static.indigodomo.com/www/css/social-buttons.css" rel="stylesheet">
    </head>
    <body>
    <div class="background">
    <!-- START navbar
    ================================================== -->
    <div class="navbar-wrapper">
      <div class="container">
        <div>
          <div class="domotics-logo"><img src="https://static.indigodomo.com/www/images/wordmark.png"/></div>
         ''' + Qrcodedata  + '''
        </div>
        </div>
        </div>       
                </body>
                '''

                # update QRcode html page on the fly here - otherwise when name is changed won't update.
                QRhttp.write(Qrcodedata)
                filepath = os.path.realpath(QRhttp.name)
                self.logger.debug("Using path {}".format(filepath))
                QRhttp.close()
                self.logger.debug(device.states["QRCode"])
                self.sleep(0.5)
                webbrowser.open_new('file://' + filepath)
            else:
                self.logger.info("No QR Code found as yet.")
        except AttributeError:
            self.logger.info("No QR Code found as yet.")
            pass

    def toggleDebugEnabled(self):
        """
        Toggle debug on/off.
        """
        self.debugLog(u"toggleDebugEnabled() method called.")
        if self.logLevel == logging.INFO:
            self.logLevel = logging.DEBUG
            self.indigo_log_handler.setLevel(self.logLevel)

            indigo.server.log(u'Set Logging to DEBUG')
        else:
            self.logLevel = logging.INFO
            indigo.server.log(u'Set Logging to INFO')
            self.indigo_log_handler.setLevel(self.logLevel)

        self.pluginPrefs[u"logLevel"] = self.logLevel
        return
        ## Triggers

        ###############  Device Selection Stuff  ######################

        ########################################
        # Publication management methods - used by the dialog used by customers to publish/unpublish devices to HomeKit.
        ########################################

    def published_list(self, *args, **kwargs):
        published = []
        for device in self.device_list:
            published.append((device.id, device.name))
        return published.sort(key=lambda x: x[1])

    ### callbacks from device selection menus

    def all_options_menuChanged(self, valuesDict, *args, **kwargs):  # typeId, devId):
        if self.debug8:
            self.logger.debug("all_options Menuchanged: returning valuesDict")
        return valuesDict

    def subtype_callback(self, valuesDict, *args, **kwargs):  # typeId, devId):
        if self.debug8:
            self.logger.debug("Subtype callback: returning valuesDict \n {}".format(valuesDict))
        return valuesDict

    def menuChanged(self, valuesDict, *args, **kwargs):  # typeId, devId):
        if self.debug8:
            self.logger.debug("menuChanged: {}".format(valuesDict))
        valuesDict["isDeviceSelected"] = False
        return valuesDict

    ### callbacks from device selection menus

    def doorbell_list_generator(self, filter="", valuesDict=None, typeId="", targetId=0):  # (self, *args, **kwargs):
        try:
            unassigned_device_list = []
            assigned_device_list = []
            for device in indigo.devices:
                if "onOffState" in device.states:  # for doorbell only use onOffState devices
                    unassigned_device_list.append((device.id, device.name))
            unassigned_device_list.sort(key=lambda x: x[1])
            assigned_device_list.sort(key=lambda x: x[1])
            device_list = []
            device_list.append((-1, "No DoorBell Device Selected"))
            device_list.append((-2, "%%disabled:Doorbell Devices available to use:%%"))
            device_list.append((-3, u"%%separator%%"))
            device_list.extend(unassigned_device_list)
            ##
            return device_list
        except:
            self.logger.exception("Caught Exception DoorBell ")

    ########################################
    def runSystem(self, values_dict, type_id="", dev_id=None):
        # self.logger.info("{}".format(values_dict))
        self.logger.info("Attempting to unquarantine Plugin files...")
        self.logger.info("Command to run (copy into terminal) if fails\n{}".format("sudo xattr -rd com.apple.quarantine '" + indigo.server.getInstallFolderPath() + "/" + "Plugins'"))
        locationofshfile = indigo.server.getInstallFolderPath() + "/" + "Plugins/HomeKitLink-Siri.indigoPlugin/Contents/Server Plugin/quarantine.sh"

    #        # locationofshfile = locationofshfile.replace(' ', '\ ')
    #         applescript1 = ('set ffmpeg to "\\\"/Library/Application Support/Perceptive Automation/Indigo 2022.1/Plugins/HomeKitL.indigoPlugin/Contents/Server Plugin/ffmpeg/ffmpeg\\\""')
    #         applescript2 = ('set myscript to "sudo /usr/bin/xattr -rd com.apple.quarantine " & ffmpeg')
    #         applescript3 = ('set myAppleScriptAsShellScript2 to "osascript -e \'do shell script \"" & myscript & "\"\'" with administrator privileges')
    #         applescript4 = ('do shell script "echo The value: " & myAppleScriptAsShellScript2')
    #         applescript5 = ('do shell script myAppleScriptAsShellScript2 with administrator privileges')
    #
    #         applescriptall = r'''
    # set ffmpeg to "\\\"/Library/Application Support/Perceptive Automation/Indigo 2022.1/Plugins/HomeKitSpawn.indigoPlugin/Contents/Server Plugin/ffmpeg/ffmpeg\\\""
    # set myscript to "sudo /usr/bin/xattr -rd com.apple.quarantine " & ffmpeg
    # set myAppleScriptAsShellScript2 to "osascript -e 'do shell script \"" & myscript & "\"'"
    # do shell script myAppleScriptAsShellScript2 with administrator privileges
    #         '''
    #         my_ascript_from_string = applescript.AppleScript(source=applescriptall)
    #         reply = my_ascript_from_string.run()
    #         self.logger.info("Reply: {}".format(reply))
    # applescript = ('do shell script ""'+str(locationofshfile)+'"" ' 'with administrator privileges')

    # exit_code = subprocess.call(['osascript', '-e', applescript1, "-e", applescript2, "-e", applescript3, "-e", applescript4, "-e",applescript5])
    # self.logger.debug(f"{exit_code}")

        path = indigo.server.getInstallFolderPath()+"/"+ "Plugins/"
        path.replace(' ', '\ ')
        command = ["xattr", "-rd","com.apple.quarantine",  path]

        cmd1 = subprocess.Popen(['echo', str(values_dict["password" ]) ], stdout=subprocess.PIPE)
        cmd2 = subprocess.Popen(['sudo', '-S'] + command, stdin=cmd1.stdout, stdout=subprocess.PIPE)
        output = cmd2.stdout.read()
        self.logger.info(output)

    def debug_device_generator(self, filter="", valuesDict=None, typeId="", targetId=0):  # (self, *args, **kwargs):
        endpoint_list = []
        endpoint_list.append((-3, "No debug device"))
        for device_id in self.device_list:
            try:
                device = self.return_deviceorAG(device_id)
                device_props = dict(device.pluginProps)
                try:
                    deviceBridgeID = int(device_props.get("HomeKit_bridgeUniqueID", 99))
                except:
                    deviceBridgeID = 99
                ## no checks here - basically can select any device to debug - even those that are no active in Homekit.
                ## Even if not active will still be able to debug the DeviceUpdate state info.
                endpoint_list.append((int(device.id), device.name))  # tuple
            except:
                self.logger.exception("Exception in Show Devices")
        self.logger.debug("List:{}".format(endpoint_list))
        return sorted(endpoint_list)

    def device_list_generator(self, filter="", valuesDict=None, typeId="", targetId=0):  # (self, *args, **kwargs):
        try:
            unassigned_device_list = []
            assigned_device_list = []
            assigned_another_bridgelist = []  # seperate out devices published by another bridge.
            isdevorAG = valuesDict.get("selectdevice_or_AG", "device")
            NametoUse = "Devices"
            try:
                bridgeuniqueID = int(valuesDict.get("bridgeUniqueID", 99))
            except ValueError:
                bridgeuniqueID = 99

            if self.debug8:
                self.logger.debug("Device list Generator:\n valuesDict {} \n typeId {}".format(valuesDict, typeId))
            if isdevorAG == "device":
                NametoUse = "Devices"
                for device in indigo.devices:
                    if device.id in self.device_list:
                        device_name = device.name
                        ## is assigned to a bridgeget bridge it is assigned to
                        try:
                            bridgeassigned = int(device.pluginProps.get("HomeKit_bridgeUniqueID", 99))  ## shouldnt ever =99
                        except ValueError:
                            bridgeassigned = 99
                        if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                            assigned_device_list.append((device.id, device_name))
                        else:  ## assigned but by another Bridge.
                            assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + str(device_name) + ":%%"))  ## disabled selection
                    else:
                        unassigned_device_list.append((device.id, device.name))
            elif isdevorAG == "action_group":
                NametoUse = "Action Groups"
                for actionGroup in indigo.actionGroups:
                    if actionGroup.id in self.device_list:
                        actionG_name = actionGroup.name
                        try:
                            bridgeassigned = actionGroup.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                        except ValueError:
                            bridgeassigned = 99  ## shouldnt ever =99.

                        if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                            assigned_device_list.append((actionGroup.id, actionG_name))
                        else:  ## assigned but by another Bridge.
                            assigned_another_bridgelist.append((actionGroup.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + (actionG_name) + ":%%"))  ## disabled selection
                    else:
                        unassigned_device_list.append((actionGroup.id, actionGroup.name))
            elif isdevorAG == "BI_camera":
                NametoUse = "Blue Iris Cameras"
                for device in indigo.devices:
                    if device.pluginId == "com.GlennNZ.indigoplugin.BlueIris":
                        # self.logger.info("{}".format(device.model) )
                        if device.model == "BlueIris Camera":
                            if device.id in self.device_list:
                                device_name = device.name
                                try:
                                    bridgeassigned = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                                except ValueError:
                                    bridgeassigned = 99  ## shouldnt ever =99
                                if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                                    assigned_device_list.append((device.id, device_name))
                                else:  ## assigned but by another Bridge.
                                    assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + str(device_name) + ":%%"))  ## disabled selection
                            else:
                                unassigned_device_list.append((device.id, device.name))
            elif isdevorAG == "lights":
                NametoUse = "Lights"
                for device in indigo.devices:
                    if hasattr(device, "brightness"):
                        if device.id in self.device_list:
                            device_name = device.name
                            try:
                                bridgeassigned = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                            except ValueError:
                                bridgeassigned = 99  ## shouldnt ever =99
                            if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                                assigned_device_list.append((device.id, device_name))
                            else:  ## assigned but by another Bridge.
                                assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + str(device_name) + ":%%"))  ## disabled selection
                        else:
                            unassigned_device_list.append((device.id, device.name))
            elif isdevorAG == "SS_camera":
                NametoUse = "Security Spy Cameras"
                for device in indigo.devices:
                    if device.pluginId == "org.cynic.indigo.securityspy":
                        # self.logger.info("{}".format(device.model) )
                        if device.model == "Camera":
                            if device.id in self.device_list:
                                device_name = device.name
                                bridgeassigned = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                                if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                                    assigned_device_list.append((device.id, device_name))
                                else:  ## assigned but by another Bridge.
                                    assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + (device_name) + ":%%"))  ## disabled selection
                            else:
                                unassigned_device_list.append((device.id, device.name))
            elif isdevorAG == "switch":
                NametoUse = "Relays"
                for device in indigo.devices:
                    if type(device) == indigo.RelayDevice:  ## use relay
                        if device.id in self.device_list:
                            device_name = device.name
                            ## is assigned to a bridgeget bridge it is assigned to
                            bridgeassigned = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                            if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                                assigned_device_list.append((device.id, device_name))
                            else:  ## assigned but by another Bridge.
                                assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + str(device_name) + ":%%"))  ## disabled selection
                        else:
                            unassigned_device_list.append((device.id, device.name))
            elif isdevorAG == "sensor":
                NametoUse = "Sensors"
                for device in indigo.devices:
                    if type(device) == indigo.SensorDevice:  ## use relay
                        if device.id in self.device_list:
                            device_name = device.name
                            ## is assigned to a bridgeget bridge it is assigned to
                            try:
                                bridgeassigned = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)  ## shouldnt ever =99
                            except ValueError:
                                bridgeassigned = 99  ## shouldnt ever =99
                            if int(bridgeassigned) == bridgeuniqueID:  ## device assigned to this bridge can access
                                assigned_device_list.append((device.id, device_name))
                            else:  ## assigned but by another Bridge.
                                assigned_another_bridgelist.append((device.id, "%%disabled:" + "Bridge Id: " + str(bridgeassigned) + " " + str(device_name) + ":%%"))  ## disabled selection
                        else:
                            unassigned_device_list.append((device.id, device.name))

            unassigned_device_list.sort(key=lambda x: x[1])
            assigned_device_list.sort(key=lambda x: x[1])
            assigned_another_bridgelist.sort(key=lambda x: x[1])
            # if self.debug8:
            # self.logger.debug("\nUnassigned list: {}\nAssigned List {}\nAssigned Another Bridge{}".format(unassigned_device_list,assigned_device_list, assigned_another_bridgelist))
            device_list = []

            if len(unassigned_device_list):
                device_list.append((-1, "%%disabled:" + str(NametoUse) + " available for publishing to HomeKit:%%"))
                device_list.extend(unassigned_device_list)
                device_list.append((-2, u"%%separator%%"))

            if len(assigned_device_list):
                device_list.append((-3, "%%disabled:" + str(NametoUse) + "  on this Bridge published to HomeKit:%%"))
                device_list.extend(assigned_device_list)
                device_list.append((-4, u"%%separator%%"))

            if len(assigned_another_bridgelist):
                device_list.append((-5, "%%disabled:" + str(NametoUse) + " on other Bridges published to HomeKit:%%"))
                device_list.extend(assigned_another_bridgelist)
                device_list.append((-6, u"%%separator%%"))
            ##
            # if self.debug8:
            # self.logger.debug("Device_list:{}".format(device_list))
            return device_list
        except:
            self.logger.exception("")

        #
        # Detect a HomeKit type from an Indigo type
        # Based on Homekit brige - reasonable, quick starting point - a lot more work needed thought
        # regardless everything is user selectable - with advanced button - this should just be a guide
        # so no pivotal is completely right.
        #

    def detectHomeKitType(self, objId):
        try:
            if objId in indigo.actionGroups:
                return "service_Switch"

            dev = indigo.devices[objId]

            if dev.pluginId == "com.perceptiveautomation.indigoplugin.zwave" and dev.deviceTypeId == "zwLockType":
                return "service_LockMechanism"

            if dev.pluginId == "com.perceptiveautomation.indigoplugin.airfoilpro" and dev.deviceTypeId == "speaker":
                return "service_Speaker"

            if dev.pluginId == "com.pennypacker.indigoplugin.senseme":
                return "service_Fanv2"

            if dev.pluginId in ("com.boisypitre.vss","com.GlennNZ.indigoplugin.ParadoxAlarm","com.frightideas.indigoplugin.dscAlarm","com.berkinet.ad2usb"):
                return "service_Security"



            if dev.model == "BlindsT1234":
                return "service_WindowCovering"
            elif "Shutter" in dev.model:
                return "service_WindowCovering"

            if dev.pluginId == "com.fogbert.indigoplugin.fantasticwWeather":
                if dev.deviceTypeId == 'Weather': return "service_TemperatureSensor"
                if dev.deviceTypeId == 'Daily': return "service_HumiditySensor"

            if dev.pluginId == "com.GlennNZ.indigoplugin.BlueIris" or dev.pluginId == "org.cynic.indigo.securityspy":
                return "service_Camera"

            elif dev.displayStateImageSel == "TemperatureSensor":
                return "service_TemperatureSensor"

            elif "temperature" in dev.states:
                return "service_TemperatureSensor"

            elif dev.subModel == "Temperature":
                return "service_TemperatureSensor"

            elif dev.subModel == "Humidity":
                return "service_HumiditySensor"

            elif "brightnessLevel" in dev.states and "brightness" in dir(dev):
                if dev.supportsRGB:
                    return "service_Lightbulb"
                    ## not useful return "service_RGBLightbulb"
                else:
                    return "service_Lightbulb"

            elif "Outlet" in dev.model:
                return "service_Outlet"

            elif "speedIndex" in dir(dev):
                return "service_Fanv2"

            elif "sensorInputs" in dir(dev):
                if "protocol" in dir(dev) and str(dev.protocol) == "Insteon" and dev.model == "I/O-Linc Controller":
                    return "service_GarageDoorOpener"

                else:
                    return "service_GarageDoorOpener"

            elif "sensorValue" in dir(dev):
                if str(dev.protocol) == "Insteon" and "Motion Sensor" in dev.model:
                    return "service_MotionSensor"

                elif dev.pluginId == "com.perceptiveautomation.indigoplugin.zwave" and dev.deviceTypeId == "zwValueSensorType" and "LightSensor" in str(dev.displayStateImageSel):
                    return "service_LightSensor"

                elif "Leak" in dev.model:
                    return "service_LeakSensor"

                elif "Smoke" in dev.model:
                    return "service_SmokeSensor"

                elif "Humidity" in dev.model:
                    return "service_HumiditySensor"

                else:
                    return "service_MotionSensor"

            elif "supportsCoolSetpoint" in dir(dev):
                return "service_Thermostat"

            elif "zoneCount" in dir(dev):
                return "service_IrrigationSystem"

            else:
                # Fallback but only if there is an onstate, otherwise we return an unknown
                if "onState" in dir(dev):
                    return "service_Switch"
                else:
                    self.logger.warning(u"{} is defaulting to a HomeKit switch because the device type cannot be determined.  Select Use All to manually adjust with care".format(dev.name))
                    return "service_Switch"
                # return "Dummy"

        except Exception as e:
            self.logger.exception("Error in HomeKit device types")

    def subtype_generator(self, filter="", values_dict=None, *args, **kwargs):
        try:
            if self.debug8:
                self.logger.debug("subtype Generator/HomeKit Device Type. ValuesDict:{}".format(values_dict))

            showALL = values_dict.get("showALL", False)
            subtype_list = []
            if showALL:  ## return every subtype
                subtypestoReturn = list(self.homeKitSubTypes.values())
                flat_list_duplicates = [val for sublist in subtypestoReturn for val in sublist]
                subtypestoReturnnoDuplicates = []
                for value in flat_list_duplicates:
                    if value not in subtypestoReturnnoDuplicates:
                       subtypestoReturnnoDuplicates.append(value)
                #flat_list = [val for sublist in subtypestoReturnnoDuplicates for val in sublist]
                return subtypestoReturnnoDuplicates

            if "deviceId" in values_dict:
                if values_dict["deviceId"] != "":
                    if int(values_dict["deviceId"]) > 0:
                        device = self.return_deviceorAG(int(values_dict["deviceId"]))
                        selectedsubType = device.pluginProps.get("HomeKit_deviceSubtype", "")  # get user selected subtype.
                        published = device.pluginProps.get("HomeKit_publishDevice", False)  ## check if published if not - then can return all.
                        if selectedsubType != "" and published:
                            if self.debug8:
                                self.logger.debug("Subtype set by user, returning that. Rightly or Wrongly.")
                            return [selectedsubType]  ## TODO search list and present all options within list
                        detecttype = self.detectHomeKitType(int(values_dict["deviceId"]))
                        if self.debug8:
                            self.logger.debug("Detected Type:{}".format(detecttype))
                        if detecttype in self.homeKitSubTypes:
                            values_dict["deviceSubtype"] = self.homeKitSubTypes[detecttype][0]  # select first list -- fails delete me
                            return self.homeKitSubTypes[detecttype]
                        subtype_list.append(("invalid", "invalid device type"))
            else:
                subtype_list.append(("invalid", "invalid device type"))
            return subtype_list  # self.subTypesSupported
        except:
            self.logger.debug("Caught Exception subtypes:", exc_info=True)

    def devicestate_generator(self, filter="", values_dict=None, *args, **kwargs):
        try:
            state_list = []
            if "deviceId" in values_dict:
                try:
                    device = indigo.devices[int(values_dict["deviceId"])]
                    states = dict(device.states)
                    if len(states) > 0:
                        for key, value in states.items():
                            state_list.append((key, key + str(" == '" + str(value) + "'")))
                except:
                    state_list.append(("invalid", "invalid device type"))

            state_list.sort(key=lambda x: x[1])
            if self.debug8:
                self.logger.debug("Device State Generator List:\n{}".format(state_list))

        except TypeError:
            pass
            if self.debug8:
                self.logger.debug("type error skipped.")
        except:
            self.logger.debug("Caught Exception device State Generator", exc_info=True)
        return state_list

    def get_alt_name(self, device):
        homekit_name = device.pluginProps.get("homekit-name")
        if homekit_name:
            return homekit_name
        else:
            return ""

    #############################

    def return_deviceorAG(self, deviceorAGid):
        try:
            if (deviceorAGid in indigo.devices):
                deviceorAG = indigo.devices[deviceorAGid]
            else:
                deviceorAG = indigo.actionGroups[deviceorAGid]
            return deviceorAG
        except KeyError:
            self.logger.exception("Key Error:")
            return None

    ########################################
    def select_device(self, values_dict, type_id="", dev_id=None):
        self.logger.debug(u"select_device called")
        if self.debug8:
            self.logger.debug("Select Device Called and ValuesDict:\n{}".format(values_dict))
        errors_dict = indigo.Dict()
        deviceorAG = self.return_deviceorAG(int(values_dict["deviceId"]))
        try:
            device = deviceorAG
            values_dict["isDeviceSelected"] = True
            values_dict["HomeKit_publishDevice_2"] = device.pluginProps.get("HomeKit_publishDevice", False)
            values_dict["showSubtypes"] = True
            values_dict["deviceSensor"] = device.pluginProps.get("HomeKit_deviceSensor", "")  ## unless sensor device this isn't used. I believe. Hope.
            values_dict["doorbellId"] = device.pluginProps.get("HomeKit_doorbellId", "")
            values_dict["tempSelector"] = device.pluginProps.get("HomeKit_tempSelector", False)
            values_dict["inverseSelector"] = device.pluginProps.get("HomeKit_inverseSelector",False)
            values_dict["audioSelector"] = device.pluginProps.get("HomeKit_audioSelector", False)

            ## auto select correct subtype
            detecttype = self.detectHomeKitType(int(values_dict["deviceId"]))
            if self.debug8:
                self.logger.debug("Detected Type:{}".format(detecttype))
            if detecttype in self.homeKitSubTypes:
                values_dict["deviceSubtype"] = self.homeKitSubTypes[detecttype][0]
            else:
                values_dict["deviceSubtype"] = device.pluginProps.get("HomeKit_deviceSubtype", "")

            alt_name = self.get_alt_name(device)
            values_dict["altName"] = alt_name if alt_name != device.name else ""

        except KeyError:
            # No device is selected, so hide everything
            values_dict["isDeviceSelected"] = False
            values_dict["HomeKit_publishDevice_2"] = False
        return values_dict

    ########################################
    def toggle_publish(self, values_dict, type_id="", dev_id=None):
        self.logger.debug("toggle_publish called")
        if values_dict["isDeviceSelected"] and values_dict["HomeKit_publishDevice_2"]:
            values_dict["enablePublishFields"] = True
        else:
            values_dict["enablePublishFields"] = False
        return values_dict

    ########################################
    def save(self, values_dict, type_id="", dev_id=None):
        errors_dict = indigo.Dict()
        if self.debug8:
            self.logger.debug("Save Selected: \nValueDict\n{}".format(values_dict))
            ## Use this to altern sensor selection.. eg. if showall off and no sensor - set to default.
        publication_change = False
        try:
            device = self.return_deviceorAG(int(values_dict["deviceId"]))  ## device or AG
            if device == None:
                self.logger.error("Error Saving this device.")
                return
            device_props = dict(device.pluginProps)

            if values_dict["HomeKit_publishDevice_2"]:
                # Note the 2 here - in the Alexa plugin this field was the same in the device and in the pluginConfig XML
                # so when I refactored to a Device approach everything crapped out.  Was because the  Plugin Config XML device had publish_Device
                # as did the actual device selected!  Took forever to find out why!
                if values_dict["altName"] != "":
                    alternate_name = HKutils.cleanup_name_for_homekit(values_dict["altName"])
                    if device_props.get("homekit-name", "") != alternate_name:
                        device_props["homekit-name"] = alternate_name
                else:
                    ## Blank HomeKit Name
                    blankname = device.name
                    values_dict["altName"] = HKutils.cleanup_name_for_homekit(device.name)
                    if device_props.get("homekit-name", "") != blankname:
                        device_props["homekit-name"] = blankname
                if values_dict["deviceSubtype"] != "":
                    alternate_subtype = values_dict['deviceSubtype']
                    if device_props.get("HomeKit_deviceSubtype") != alternate_subtype:
                        device_props["HomeKit_deviceSubtype"] = alternate_subtype

                if values_dict["deviceSensor"] != "":
                    alternate_sensor = values_dict['deviceSensor']
                    if device_props.get("HomeKit_deviceSensor") != alternate_sensor:
                        device_props["HomeKit_deviceSensor"] = alternate_sensor
                else:
                    ## deviceSensor is blank set it appropriately
                    ## for temperature and Humidity, plus others..
                    ## only used for sensor types
                    ## can be user selected away from this default - but set default.
                    if values_dict["deviceSubtype"] != "":
                        subtype = values_dict["deviceSubtype"]
                        # TODO change to contains sensor in string - may add other problem...
                        if subtype in ("TemperatureSensor", "HumiditySensor", "OccupancySensor", "SmokeSensor", "ContactSensor", "CarbonDioxideSensor", "LightSensor", "LeakSensor", "CarbonMonoxideSensor"):
                            settoSensor = "sensorValue"
                            device_props["HomeKit_deviceSensor"] = settoSensor

                if values_dict["doorbellId"] != "":
                    alternate_sensor = values_dict['doorbellId']
                    if device_props.get("HomeKit_doorbellId") != alternate_sensor:
                        device_props["HomeKit_doorbellId"] = alternate_sensor

                if values_dict["bridgeUniqueID"] != "":
                    bridge_id = values_dict['bridgeUniqueID']
                    if device_props.get("HomeKit_bridgeUniqueID") != bridge_id:
                        device_props["HomeKit_bridgeUniqueID"] = bridge_id

                ## add temp selector
                if values_dict["tempSelector"] != "":
                    tempSelector = values_dict['tempSelector']
                    if device_props.get("HomeKit_tempSelector") != tempSelector:
                        device_props["HomeKit_tempSelector"] = tempSelector

                if values_dict["inverseSelector"] != "":
                    inverseSelector = values_dict['inverseSelector']
                    if device_props.get("HomeKit_inverseSelector") != inverseSelector:
                        device_props["HomeKit_inverseSelector"] = inverseSelector
                        ## add temp selector
                if values_dict["audioSelector"] != "":
                    audioSelector = values_dict['audioSelector']
                    if device_props.get("HomeKit_audioSelector") != audioSelector:
                        device_props["HomeKit_audioSelector"] = audioSelector

                if not device_props.get("HomeKit_publishDevice", False): publication_change = True
                self.device_list.add(device.id)
                ## this is fine - will be added to internal_list on device start - just not removed from it
                ## internal_list is add only by start/stop.
                device_props["HomeKit_publishDevice"] = True
                values_dict["enablePublishFields"] = True
                if values_dict['deviceSubtype'] != device_props.get("HomeKit_deviceSubtype", None):
                    if device_props.get("HomeKit_deviceSubtype", None) != values_dict['deviceSubtype']:
                        device_props["HomeKit_deviceSubtype"] = values_dict['deviceSubtype']
            else:
                values_dict["enablePublishFields"] = False
                if device_props.get("HomeKit_publishDevice", False): publication_change = True
                device_props = {}  ##?
                ## unpublished - delete all device props - not the Device/Bridge itself!
                device_props["HomeKit_bridgeUniqueID"] = ""
                device_props["HomeKit_deviceSubtype"] = ""
                device_props["HomeKit_deviceSensor"] = ""
                device_props["homekit-name"] = ""
                device_props["HomeKit_tempSelector"] = ""
                device_props["HomeKit_inverseSelector"] = ""
                device_props["HomeKit_audioSelector"] = ""
                try:
                    self.device_list.remove(device.id)  ## not good to just remove here and internal list no longer deleted.
                    checkindex = next((i for i, item in enumerate(self.device_list_internal) if item["deviceid"] == device.id), None)
                    if checkindex != None:
                        self.logger.info("Deleting item:{}".format(self.device_list_internal[checkindex]))
                        del self.device_list_internal[checkindex]
                        if device.id in self.device_list_internal_idonly:
                            self.device_list_internal_idonly.remove(device.id)
                    self.logger.info("Given just unpublished device to HomeKit, Bridge will need to be restarted for changes to take effect")
                except:
                    self.logger.debug("device_list remove error, Exception\n", exc_info=True)
            self.logger.debug(u"saving plugin props: \n{}".format(device_props))
            device.replacePluginPropsOnServer(indigo.Dict(device_props))

            if publication_change:
                if values_dict["enablePublishFields"]:
                    self.logger.warn("You have published a new device to HomeKit. ")
                    self.logger.warn("Once you press Save the Bridge will restart for this to take effect.")
                    self.logger.warn("Please feel free to continue to add devices meanwhile.")
                else:
                    self.logger.warn("You have removed an HomeKit Device. ")
                    self.logger.warn("After pressing Save, the Bridge will restart for this to take effect.")
                    self.logger.warn("The device should disappear from HomeKit Clients in a short space of time.")

        except Exception as exc:
            self.logger.error(u"An unknown error occurred {}".format(str(exc)))
            self.logger.debug(u"uncaught exception: \n{}", exc_info=True)

        return values_dict, errors_dict

    ########################################
    # Menu Debug Items
    ########################################
    def show_internallist(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        self.logger.info(u"{0:=^165}".format(" self device_list_internal_idonly "))
        for device in self.device_list_internal_idonly:
            self.logger.info(f"{device}")
        self.logger.info(u"{0:=^165}".format(" self device_list_internal "))
        for device in self.device_list_internal:
            self.logger.info(f"{device}")
    ####

    def bridgeListGenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
        listofallBridges = []
        myArray = []
        for device in indigo.devices:
            # ; original below ; may keep both as may be useful for HomeKit Bridge copies
            # uniqueID = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)
            # modified below
            uniqueID = 99
            spawnProps = device.globalProps.get("com.GlennNZ.indigoplugin.HomeKitSpawn")
            if spawnProps !=None:
                uniqueID = spawnProps.get("HomeKit_bridgeUniqueID", 99)
            if uniqueID != 99 and uniqueID != "":
                if int(uniqueID) not in listofallBridges:
                    listofallBridges.append(int(uniqueID))

        for device in indigo.devices:
            uniqueID = device.pluginProps.get("HomeKit_bridgeUniqueID", 99)
            if uniqueID != 99 and uniqueID != "":
                if int(uniqueID) not in listofallBridges:
                    listofallBridges.append(int(uniqueID))

        for ID in listofallBridges:
            myArray.append((ID, "Bridge ID:"+str(ID)))
       # myArray = [("option1", "First Option"), ("option2", "Second Option")]
        return myArray
    ########################################
    def menu_actionResetAccessories(self, valuesDict, typeId):
        self.logger.debug("Reset Bridge Accessories called.  valueDict {}".format(valuesDict))
        try:
            Bridgedevice = int(valuesDict["Bridge"])  ## deviceID not BridgeUniqueI
            Bridge = indigo.devices[Bridgedevice].pluginProps.get("bridgeUniqueID", 99)
            self.logger.debug("Using Path:{}".format(self.pluginprefDirectory))
            self.logger.info(f"Checking for busy_state file with UniqueID of {Bridge}")

            onlyfiles = [f for f in listdir(self.pluginprefDirectory) if isfile(join(self.pluginprefDirectory, f))]
            self.logger.debug("Found Files:{}".format(onlyfiles))

            for file in onlyfiles:
                if "busy_home" in file:
                    ## we have a suitable file
                    ## remove state
                    checknumber = file[10:]  ## remove .state
                    checknumber2 = checknumber[:-6]  ## get numbers go backwards to avoid error with smaller digits.  Also now 6 digits, so remove front and back
                    self.logger.debug("Should leave number only regardless of length of Unique ID {}".format(checknumber2))
                    if str(checknumber2) == str(Bridge):
                        ## make sure can manage old 4 digits to 9 digit numbers even thought it is only affecting me!
                        self.logger.warning(f"Found Bridge Security File {file} linked to Bridge ID {Bridge}  Deleting this file.".format(checknumber2))
                        if os.path.isfile(os.path.join(self.pluginprefDirectory, file)):
                            os.remove(os.path.join(self.pluginprefDirectory, file))
                            self.logger.warning("Deleted file {}".format(file))

            self.restartBridge()

        except:
            self.logger.exception("Caught Exception with this action")

    def menu_actionMoveAccessories(self, valuesDict, typeId):
        self.logger.info("Move Bridge Accessories called.  valueDict {}".format(valuesDict))
        try:
            toBridgedevice = int(valuesDict["toBridge"])  ## deviceID not BridgeUniqueID
            fromBridge = int(valuesDict["fromBridge"])  ## this is UniqueID as generated above

            toBridge = int(indigo.devices[toBridgedevice].pluginProps.get("bridgeUniqueID", 99))
            if toBridge == 99 or fromBridge == 99:
                self.logger.info("Error with the from Bridge or the to Bridge selection")
                return

            something_done = False

            # TODO delete below when setup new devices
            for device in indigo.devices:
                spawnProps = device.globalProps.get("com.GlennNZ.indigoplugin.HomeKitSpawn")
                if spawnProps == None:  ## no old props
                    continue
                if spawnProps.get("HomeKit_publishDevice", False):
                    try:
                        if spawnProps.get("HomeKit_bridgeUniqueID", 99) == fromBridge:
                            device_props = dict(device.pluginProps)
                            device_props["HomeKit_bridgeUniqueID"] = toBridge
                            device_props["HomeKit_deviceSensor"] = spawnProps.get("HomeKit_deviceSensor")
                            device_props["HomeKit_deviceSubtype"] = spawnProps.get("HomeKit_deviceSubtype")
                            device_props["HomeKit_publishDevice"] = True
                            device_props["homekit-name"] = spawnProps.get("homekit-name")

                            # HomeKit_bridgeUniqueID : 3283 (integer)
                            # HomeKit_deviceSensor : onOffState (string)
                            # HomeKit_deviceSubtype : OccupancySensor (string)
                            # HomeKit_deviceSubtype : false (bool)
                            # homekit-name : Occupatum Test (string)
                            self.logger.warning("Found Device {} attached to Bridge ID {}, moving to new Bridge ID {}".format(device.name, fromBridge, toBridge))
                            device.replacePluginPropsOnServer(indigo.Dict(device_props))
                            self.logger.debug("new PluginProps {}".format(device_props))
                            something_done = True
                    except:
                        self.logger.exception("Error in device update")
                        self.logger.debug("Error in device Move", exc_info=True)

            ## below keep
            for device in indigo.devices:
                if device.pluginProps.get("HomeKit_publishDevice", False):
                    try:
                        if device.pluginProps.get("HomeKit_bridgeUniqueID", 99) == fromBridge:
                            device_props = dict(device.pluginProps)
                            device_props["HomeKit_bridgeUniqueID"] = toBridge
                            self.logger.warning("Found Device {} attached to Bridge ID {}, moving to new Bridge ID {}".format(device.name, fromBridge, toBridge))
                            device.replacePluginPropsOnServer(indigo.Dict(device_props))
                            self.logger.debug("new PluginProps {}".format(device_props))
                            something_done = True
                    except:
                        self.logger.exception("Error in device update")
                        self.logger.debug("Error in device Move", exc_info=True)

            for device in indigo.actionGroups:  ## actionGroup not Device - lazy
                if device.pluginProps.get("HomeKit_publishDevice", False):
                    try:
                        if device.pluginProps.get("HomeKit_bridgeUniqueID", 99) == fromBridge:
                            device_props = dict(device.pluginProps)
                            device_props["HomeKit_bridgeUniqueID"] = toBridge
                            self.logger.warning("Found Device {} attached to Bridge {}, moving to new Bridge ID {}".format(device.name, fromBridge, toBridge))
                            device.replacePluginPropsOnServer(indigo.Dict(device_props))
                            something_done = True
                    except:
                        self.logger.exception("Error in device update")
                        self.logger.debug("Error in device Move", exc_info=True)

            if not something_done:
                self.logger.info("No device found to update.  Ended")
                return

            self.logger.info("Now restarting destination Bridge.")

            indigo.device.enable(toBridgedevice, value=False)
            self.sleep(1)
            indigo.device.enable(toBridgedevice, value=True)


        except:
            self.logger.info("Error.  Please select all items before running")
            self.logger.debug("Error", exc_info=True)
    ########################################
    def show_drivers(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        self.logger.info(u"{0:=^165}".format(" Drivers "))
        for driver in self.driver_multiple:
            self.logger.info(u"{}".format(" Driver {} :".format(driver.indigodeviceid)))

    ########################################
    def show_selfdevicelist(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        self.logger.info(u"{0:=^165}".format(" Self Device List "))
        for driver in self.device_list:
            self.logger.info(u"{0:=^165}".format(" Item {} :".format(driver)))

    ########################################
    def show_threads(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        self.logger.info(u"{0:=^165}".format(" Threads "))
        self.logger.info('Nmber of Active Threads:' + str(threading.activeCount()))
        for thread in self.driverthread_multiple:
            self.logger.info(u"{0:=^165}".format(" Thread {} :".format(thread.name)))

    ########################################
    ########################################
    def show_bridges(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        self.logger.info(u"{0:=^165}".format(" Bridges "))
        for bridge in self.bridge_multiple:
            self.logger.info(" Bridge {} :".format(bridge.indigodeviceid))
            for accessories in bridge.accessories:
                self.logger.info(f" Accessory {accessories}")

    ########################################
    def show_device_publications(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        listofallBridges = []  # list of devices which exists, enabled or otherwise.
        for device in indigo.devices.iter("self"):
            try:
                uniqueID = int(device.pluginProps.get("bridgeUniqueID", 99))
            except ValueError:
                uniqueID = 99
            if uniqueID != 99:
                if int(uniqueID) not in listofallBridges:
                    listofallBridges.append(int(uniqueID))

        endpoint_list = []
        for device_id in self.device_list:
            datatoappend = ""
            try:
                device = self.return_deviceorAG(device_id)
                device_props = dict(device.pluginProps)
                devicename = device_props.get("homekit-name", "")
                deviceType = device_props.get("HomeKit_deviceSubtype", "")
                devicesensor = device_props.get("HomeKit_deviceSensor", "")
                try:
                    deviceBridgeID = int(device_props.get("HomeKit_bridgeUniqueID", 99))
                except ValueError:
                    deviceBridgeID = 99
                devicedoorbell = device_props.get("HomeKit_doorbellId", "-1")
                if str(devicedoorbell) == "-1":
                    devicedoorbell = "- None Selected -"
                datatoappend = "{0:<20} {1:<50} {2:<40} {3:<20}".format(device.id, device.name, devicename, deviceType)
                if "Sensor" in deviceType:
                    datatoappend = datatoappend + " {0:<20}".format(devicesensor)
                elif devicedoorbell != "":
                    datatoappend = datatoappend + " {0:<20}".format(devicedoorbell)
                if deviceBridgeID !=99:
                    endpoint_list.append((int(deviceBridgeID), datatoappend))  # tuple
            except:
                self.logger.exception("Exception in Show Devices")

        self.logger.info(u"{0:=^165}".format(" Currently Published Devices / Action Groups "))
        self.logger.info("{0:<20} {1:<20} {2:<50} {3:<40} {4:<20} {5:<20}".format("BridgeID", "DeviceID", "Device Name", "HomeKit Name", "Device Type", "Sensor Type/Linked Doorbell"))
        self.logger.info(u"{0:-^165}".format("-"))

        for endpoint in sorted(endpoint_list):
            if int(endpoint[0]) not in self.deviceBridgeNumber:
                if int(endpoint[0]) not in listofallBridges:
                    bridgemsg = "Missing ID:{}".format(endpoint[0])
                    self.logger.error("{0:<20} {1}".format(bridgemsg,endpoint[1]))
                ## not enabled or doesn't exist.. differentiate
                else:
                    bridgemsg = "Disabled ID:{}".format(endpoint[0])
                    self.logger.warning("{0:<20} {1}".format(bridgemsg, endpoint[1]))
            else:
                bridgemsg = "Bridge ID:" + str(endpoint[0])
                self.logger.info("{0:<20} {1}".format(bridgemsg, endpoint[1]))
        self.logger.info(u"{0:=^165}".format(" {} HomeKit Device Found".format(len(endpoint_list))))
        self.logger.info(u"{0:=^165}".format(" Thats the end of Published Devices / Action Groups "))

    #######################################
    # Menu Items
    ########################################
    def delete_isolated_devices(self, *args, **kwargs):
        ## modify to only delete if bridge does not exist
        ## Not disabled bridges for example
        listofallBridges = []
        for device in indigo.devices.iter("self"):
            try:
                uniqueID = int(device.pluginProps.get("bridgeUniqueID", 99))
            except ValueError:
                uniqueID = 99
            if uniqueID != 99:
                if int(uniqueID) not in listofallBridges:
                    listofallBridges.append(int(uniqueID))
        ## current list of self bridge ID.  Now scan the full device_list
        isolated_device_found = False
        for device_id in self.device_list:
            try:
                device = self.return_deviceorAG(device_id)
                device_props = dict(device.pluginProps)
                devicename = device_props.get("homekit-name", "")
                try:
                    deviceBridgeID = int(device_props.get("HomeKit_bridgeUniqueID", 99))
                except ValueError:
                    continue
                    # move to next device as this one blank
                if deviceBridgeID not in listofallBridges:  ## Current Bridge not enabled, deleted or stopped
                    isolated_device_found = True
                    self.logger.warning("Isolated Device Found and HomeKit linkage to be removed. Device Name {} ".format(devicename))
                    device_props["HomeKit_publishDevice"] = False
                    device_props["HomeKit_bridgeUniqueID"] = ""
                    device_props["HomeKit_deviceSubtype"] = ""
                    device_props["HomeKit_deviceSensor"] = ""
                    device_props["homekit-name"] = devicename   ## leave name same.
                    device.replacePluginPropsOnServer(indigo.Dict(device_props))
            except:
                self.logger.exception("Problem with delete / unlinking isolated devices")

        if isolated_device_found == False:
            self.logger.info("No orphaned devices found to have HomeKit linkage removed.  Full list follows below.")

        self.update_deviceList()
        self.show_device_publications()

    def delete_busy_home(self, *args, **kwargs):
        # Write all published devices to the event log with their friendly name
        listofstateids = []
        for device in indigo.devices.iter("self"):
            # if device.enabled:  ## enabled or disabled if exists want to save state file
            try:
                uniqueID = int(device.pluginProps.get("bridgeUniqueID", 99))
            except ValueError:
                uniqueID = 99
            if uniqueID != 99:
                listofstateids.append(str(uniqueID))
        self.logger.debug("Found devices with these matching IDs:{}".format(listofstateids))
        ## format file is busy_home_1232.state - check against the 1232 only
        self.logger.debug("Using Path:{}".format(self.pluginPath))
        onlyfiles = [f for f in listdir(self.pluginprefDirectory) if isfile(join(self.pluginprefDirectory, f))]

        self.logger.debug("Found Files:{}".format(onlyfiles))

        for file in onlyfiles:
            if "busy_home" in file:
                ## we have a suitable file
                ## remove state
                checknumber = file[10:]  ## remove .state
                checknumber2 = checknumber[:-6]  ## get numbers go backwards to avoid error with smaller digits.  Also now 6 digits, so remove front and back
                self.logger.debug("Should leave number only regardless of length of Unique ID {}".format(checknumber2))
                if len(checknumber2) >= 4:
                    ## make sure can manage old 4 digits to 9 digit numbers even thought it is only affecting me!
                    if str(checknumber2) not in listofstateids:
                        self.logger.warning("No HomeKitLink-Siri Bridge with an ID {}.  Must be orphaned.  Deleting this file.".format(checknumber2))
                        if os.path.isfile(os.path.join(self.pluginprefDirectory, file)):
                            os.remove(os.path.join(self.pluginprefDirectory, file))
                            self.logger.warning("Deleted file {}".format(file))
                    else:
                        self.logger.debug("HomeKitLink-Siri Bridge with unique ID {} exists.  Moving On.".format(checknumber2))

    def restartBridge(self, *args, **kwargs):
        self.logger.info("Restart all Bridges.")
        for device in indigo.devices.iter("self"):
            ## only turn on, turn off if device already on.
            if device.enabled:
                indigo.device.enable(device.id, value=False)
                self.sleep(4)
                indigo.device.enable(device.id, value=True)
            self.sleep(1)
        return

        # ## stop the homekit driver
        # for driver in self.driver_multiple:
        #     driver.stop()
        # for bridge in self.bridge_multiple:
        #     bridge.stop()
        # self.sleep(3)
        # for threads in self.driverthread_multiple:
        #     threads.join(timeout=5)
        #     if threads.is_alive():
        #         self.logger.debug("{} Thread is still alive. Timeout occured. Killing.".format(threads.name))
        #         self.logger.info("Restarting Plugin as thread not behaving.")
        #         self.restartPlugin()
        #
        # self.logger.info("Completing full Bridge(s) Shutdown...")
        # self.sleep(2)
        # ## update all devices and start Bridge again.
        # self.driver_multiple = []
        # self.bridge_multiple = []
        # self.driverthread_multiple = []
        #
        # self.update_deviceList()
        # self.startBridge()
        ## probably don't need this is full restarting able to happen
        # self.driver.async_add_job(self.driver.config_changed())

    ########################################
    ##
    def restartPlugin(self):
        # indigo.server.log(u"restart Plugin Called.")
        plugin = indigo.server.getPlugin('com.GlennNZ.indigoplugin.HomeKitLink-Siri')
        plugin.restart()

    #######################################
    ## More Menu Items
    #######################################
    def Menu_dump_accessories(self, *args, **kwargs):
        self.logger.debug("Dump accessories called...")
        self.logger.info(u"{0:=^130}".format(" Accessories Follow "))
        for num in range(0, len(self.bridge_multiple)):
            self.logger.info("*** Next HomeKit Bridge ***")
            if self.debug6:
                self.logger.debug("{}".format(self.bridge_multiple[num].accessories))
            self.logger.info("{" + "\n".join("{!r}: {!r},".format(k, v) for k, v in self.bridge_multiple[num].accessories.items()) + "}")

    def Menu_reset_pairing(self, *args, **kwargs):
        self.logger.debug("reset Paired Clients called...")
        self.logger.info("{}".format())

    def Menu_Crash(self, *args, **kwargs):
        self.logger.debug("Crash Homekit Called... ..")

    def Menu_runffmpeg(self, *args, **kwargs):
        self.logger.debug("runffmpeg Called...")
        # democall = ['./ffmpeg/ffmpeg', '-rtsp_transport', 'tcp', '-probesize', '32', '-analyzeduration', '0', '-re', '-i', 'rtsp://test:DR7yhrheu5@192.168.1.208:801/Back1&stream=2&fps=15&kbps=299', '-map', '0:0', '-c:v', 'copy', '-preset', 'ultrafast', '-tune', 'zerolatency', '-pix_fmt', 'yuv420p', '-color_range', 'mpeg', '-f', 'rawvideo', '-r', '15', '-b:v', '299k', '-bufsize', '2392k', '-maxrate', '299k', '-payload_type', '99', '-ssrc', '3961695', '-f', 'rtp', '-srtp_out_suite', 'AES_CM_128_HMAC_SHA1_80', '-srtp_out_params', 'ztkVCV7ooxnJDDyucPR1pMwY9C38gkDd15OdxfLI', 'srtp://192.168.1.28:51243?rtcpport=51243&localrtcpport=51243&pkt_size=1316', '-map', '0:1?', '-vn', '-c:a', 'libfdk_aac', '-profile:a', 'aac_eld', '-flags', '+global_header', '-f', 'null', '-ac', '1', '-ar', '16k', '-b:a', '24k', '-bufsize', '96k', '-payload_type', '110', '-ssrc', '4265106', '-f', 'rtp', '-srtp_out_suite', 'AES_CM_128_HMAC_SHA1_80', '-srtp_out_params', 'R1IzVHfcmj5WQEaC4cw67HlAlXuilvkWD/ShsiJW', 'srtp://192.168.1.28:62585?rtcpport=62585&localrtcpport=62585&pkt_size=188']
        # self.ffmpeg_lastCommand = democall
        self.logger.info(u"{0:=^130}".format(" Run Ffmpeg Command "))
        self.logger.info("This will rerun the last ffmpeg video command so that output can be checked for errors and reviewed.")
        self.logger.info("If you haven't opened a stream it will be blank.  It may freeeze and need plugin to be restarted....")
        self.logger.info("It will try for 15 seconds, any longer and something is up....")
        self.logger.info("Command List to run :")
        self.logger.info("{}".format(self.ffmpeg_lastCommand))
        if len(self.ffmpeg_lastCommand) == 0:
            self.logger.info("Seems like command empty ending.")
            return
        p1 = subprocess.Popen(self.ffmpeg_lastCommand, stderr=subprocess.PIPE, universal_newlines=True)
        try:
            outs, errs = p1.communicate(timeout=15)  # will raise error and kill any process that runs longer than 60 seconds
        except subprocess.TimeoutExpired as e:
            p1.kill()
            outs, errs = p1.communicate()
            self.logger.info("{}".format(outs))
            self.logger.warning("{}".format(errs))

        self.logger.info(u"{0:=^130}".format(" Run Ffmpeg Command Ended  "))
        self.logger.info(u"{0:=^130}".format(" Hopefully this provides some troubleshooting help  "))
