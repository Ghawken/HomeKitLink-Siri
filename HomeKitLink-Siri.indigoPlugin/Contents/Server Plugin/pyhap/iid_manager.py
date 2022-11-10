"""Module for the IIDManager class."""
from __future__ import annotations
import logging
import tempfile
import json
import os
from uuid import UUID
from pyhap.characteristic import Characteristic
from pyhap.service import Service
from .util import uuid_to_hap_type

IID_MANAGER_STORAGE_VERSION = 2
IID_MANAGER_SAVE_DELAY = 2

ALLOCATIONS_KEY = "allocations"
ACCESSORY_INFORMATION_SERVICE = "3E"

IID_MIN = 1
IID_MAX = 18446744073709551615

logger = logging.getLogger("Plugin.HomeKit_pyHap")


class IIDManager:
    """Maintains a mapping between Service/Characteristic objects and IIDs."""

    def __init__(self):
        """Initialize an empty instance."""
        self.counter = 0
        self.iids = {}
        self.objs = {}

    def assign(self, obj):
        """Assign an IID to given object. Print warning if already assigned.
        :param obj: The object that will be assigned an IID.
        :type obj: Service or Characteristic
        """
        if obj in self.iids:
            logger.warning(
                "The given Service or Characteristic with UUID %s already "
                "has an assigned IID %s, ignoring.",
                obj.type_id,
                self.iids[obj],
            )
            return

        iid = self.get_iid_for_obj(obj)
        self.iids[obj] = iid
        self.objs[iid] = obj


    def get_obj(self, iid):
        """Get the object that is assigned the given IID."""
        return self.objs.get(iid)

    def get_iid(self, obj):
        """Get the IID assigned to the given object."""
        #logger.error(f"get_iid = {self.iids.get(obj)}")
        return self.iids.get(obj)

    def get_iid_for_obj(self, obj):
        """Get the IID for the given object.
        Override this method to provide custom IID assignment.
        """
        self.counter += 1
        return self.counter

    def remove_obj(self, obj):
        """Remove an object from the IID list."""
        iid = self.iids.pop(obj, None)
        if iid is None:
            logger.error("Object %s not found.", obj)
            return None
        del self.objs[iid]
        return iid

    def remove_iid(self, iid):
        """Remove an object with an IID from the IID list."""
        obj = self.objs.pop(iid, None)
        if obj is None:
            logger.error("IID %s not found.", iid)
            return None
        del self.iids[obj]
        return obj

class AccessoryIIDStorage:
    """
    Provide stable allocation of IIDs for the lifetime of an accessory.
    Will generate new ID's, ensure they are unique and store them to make sure they
    persist over reboots.
    """

    def __init__(self, entry_id: str, file_location : str, isDebug : bool) -> None:
        """Create a new iid store."""
        self.allocations: dict[str, dict[str, int]] = {}
        self.allocated_iids: dict[str, list[int]] = {}
        self.entry_id = entry_id
        self.isDebug = isDebug
        self.file_name = file_location+"_v"+str(IID_MANAGER_STORAGE_VERSION)
        logger.debug(f"Init of AccessoryIDStorage")
        if isDebug:
            logger.debug("AccessoryIIDStorage Debuging is enabled.  Changed in pluigin Config Debug9")

    def startup(self):
        self.allocations = self.load(self.file_name)
        if self.allocations !=None:
            for aid_str, allocations in self.allocations.items():
                self.allocated_iids[aid_str] = sorted(allocations.values())
        else:
            ## blank file
            if self.isDebug:
                logger.debug("No file found.  Setting everything to empty and reallocating freshly.")
            self.allocated_iids: dict[str, list[int]] = {}
            self.allocations: dict[str, dict[str, int]] = {}
        logger.debug(f"OS16.2 Initiated AccessoryIIDStorage {self.allocations}")

    def get_or_allocate_iid(
        self,
        aid: int,
        service_uuid: UUID,
        service_unique_id: str | None,
        char_uuid: UUID | None,
        char_unique_id: str | None,
    ) -> int:
        """Generate a stable iid."""

        service_hap_type: str = uuid_to_hap_type(service_uuid)
        char_hap_type: str | None = uuid_to_hap_type(char_uuid) if char_uuid else None
        # Allocation key must be a string since we are saving it to JSON
        allocation_key = (
            f'{aid}_{service_hap_type}_{service_unique_id or ""}_'
            f'{char_hap_type or ""}_{char_unique_id or ""}'
        )

        if self.isDebug:
            logger.debug(f"IID Get or Allocation:  Allocation Key: {allocation_key}")

        aid_str = str(aid)
        accessory_allocation = self.allocations.setdefault(aid_str, {})
        accessory_allocated_iids = self.allocated_iids.setdefault(aid_str, [])
        if service_hap_type == ACCESSORY_INFORMATION_SERVICE and char_uuid is None:
            return 1
        if allocation_key in accessory_allocation:
            return accessory_allocation[allocation_key]
        if accessory_allocated_iids:
            allocated_iid = accessory_allocated_iids[-1] + 1
        else:
            allocated_iid = 2
        accessory_allocation[allocation_key] = allocated_iid
        accessory_allocated_iids.append(allocated_iid)

        self.persist()
        if self.isDebug:
            logger.debug(f"IID Get or Allocation:  Allocation Key: {allocation_key}, and allocated_iid {allocated_iid}")

        return allocated_iid

    def load(self, file_name):
        try:
            with open(file_name, "r", encoding="utf8") as file_handle:
                loaded = json.load(file_handle)
                if self.isDebug:
                    logger.debug(f"iid_manager: loaded file:{file_handle} \n{loaded}")
            if ALLOCATIONS_KEY in loaded:
                return loaded
            else:
                return {}
        except:
            logger.exception("Exception in load IID files")
            self.persist()
            return None

    def persist(self):
        tmp_filename = None
        try:
            temp_dir = os.path.dirname(self.file_name)
            with tempfile.NamedTemporaryFile( mode="w", dir=temp_dir, delete=False) as file_handle:
                tmp_filename = file_handle.name
                json.dump(self.allocations, file_handle, ensure_ascii=False, indent=4)
            os.replace(tmp_filename, self.file_name)
        except:
            logger.exception("Failed to persist accessory state")
            raise
        finally:
            if tmp_filename and os.path.exists(tmp_filename):
                os.remove(tmp_filename)


class HomeIIDManager(IIDManager):  # type: ignore[misc]
    """IID Manager that remembers IIDs between restarts."""

    def __init__(self, iid_storage: AccessoryIIDStorage, isDebug) -> None:
        """Initialize a IIDManager object."""
        super().__init__()
        self._iid_storage = iid_storage
        self.isDebug = isDebug
        logger.debug(f"OS16.2 Initated HOMEIIDManager. {iid_storage}")
        if isDebug:
            logger.debug("Home IIDManager Debuging is enabled.  Changed in pluigin Config Debug9")

    def get_iid_for_obj(self, obj: Characteristic | Service) -> int:
        """Get IID for object."""
        aid = obj.broker.aid
        if isinstance(obj, Characteristic):
            service = obj.service
            iid = self._iid_storage.get_or_allocate_iid(
                aid, service.type_id, service.unique_id, obj.type_id, obj.unique_id
            )
        else:
            iid = self._iid_storage.get_or_allocate_iid(
                aid, obj.type_id, obj.unique_id, None, None
            )
        if iid in self.objs:
            raise RuntimeError(
                f"Cannot assign IID {iid} to {obj} as it is already in use by: {self.objs[iid]}"
            )
        return iid