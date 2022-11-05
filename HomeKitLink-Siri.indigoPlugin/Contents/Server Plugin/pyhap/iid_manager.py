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

IID_MANAGER_STORAGE_VERSION = 1
IID_MANAGER_SAVE_DELAY = 2

ALLOCATIONS_KEY = "allocations"

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

        self.counter += 1
        self.iids[obj] = self.counter
        self.objs[self.counter] = obj

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

    def __init__(self, entry_id: str, file_location : str) -> None:
        """Create a new iid store."""
        self.allocations: dict[str, int] = {}
        self.allocated_iids: list[int] = []
        self.entry_id = entry_id
        self.file_name = file_location
        self.allocations = self.load(self.file_name)
        if self.allocations !=None:
            self.allocated_iids = sorted(self.allocations.values())
        else:
            self.allocated_iids = None
        logger.error(f"OS16.2 Initiated AccessoryIIDStorage {self.allocations}")

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
        logger.error(f"OS16.2 {allocation_key}")
        if allocation_key in self.allocations:
            return self.allocations[allocation_key]
        next_iid = self.allocated_iids[-1] + 1 if self.allocated_iids else 1
        self.allocations[allocation_key] = next_iid
        self.allocated_iids.append(next_iid)
        self.persist()
        return next_iid

    def load(self, file_name):
        try:
            with open(file_name, "r", encoding="utf8") as file_handle:
                loaded = json.load(file_handle)
                logger.error(f"OS16.2 iid_manager: loaded {loaded}")
            if ALLOCATIONS_KEY in loaded:
                return loaded[ALLOCATIONS_KEY]
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

    def _data_to_save(self) -> dict[str, dict[str, int]]:
        """Return data of entity map to store in a file."""
        return {ALLOCATIONS_KEY: self.allocations}

class HomeIIDManager(IIDManager):  # type: ignore[misc]
    """IID Manager that remembers IIDs between restarts."""

    def __init__(self, iid_storage: AccessoryIIDStorage) -> None:
        """Initialize a IIDManager object."""
        super().__init__()
        self._iid_storage = iid_storage
        logger.error(f"OS16.2 Initated HOMEIIDManager. {iid_storage}")

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
        logger.error(f"OS16.2 HomeIIDManager return iid {iid}")
        return iid