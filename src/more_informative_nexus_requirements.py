from typing import Dict, List
from .bridge_client import MO2BridgeClient

def getModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets all mod ids."""
    try:
        mods = client.call("batch.getFullModList")
    except Exception as e:
        print(f"Error fetching full mod list: {e}")
        return {"nexus_ids": []}

    nexus_ids: List[int] = []
    if mods:
        for mod in mods:
            try:
                nid = mod.get("nexus_id")
                if nid:
                    nexus_ids.append(nid)
            except Exception as e:
                print(f"Error reading Nexus ID from {mod}: {e}")

    return {"nexus_ids": nexus_ids}


def getEnabledModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets enabled mod ids."""
    try:
        mods = client.call("batch.getFullModList")
    except Exception as e:
        print(f"Error fetching mod list for enabled mods: {e}")
        return {"enabled_ids": []}

    enabled_ids: List[int] = []
    if mods:
        for mod in mods:
            try:
                state = mod.get("state")
                nid = mod.get("nexus_id")
                is_enabled = state & 2 # 2 is the bitmask for enabled mods
                if is_enabled and nid: 
                    enabled_ids.append(nid)
            except Exception as e:
                print(f"Error reading enabled Nexus ID from {mod}: {e}")

    return {"enabled_ids": enabled_ids}


def getTrackedModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets tracked mod ids."""
    try:
        mods = client.call("batch.getFullModList")
    except Exception as e:
        print(f"Error fetching mod list for tracked mods: {e}")
        return {"tracked_ids": []}

    tracked_ids: List[int] = []
    if mods:
        for mod in mods:
            try:
                nid = mod.get("nexus_id")
                is_tracked = bool(mod.get("is_tracked"))
                if is_tracked and nid:
                    tracked_ids.append(nid)
            except Exception as e:
                print(f"Error reading tracked Nexus ID from {mod}: {e}")

    return {"tracked_ids": tracked_ids}


def getEndorsedModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets endorsed mod ids."""
    try:
        mods = client.call("batch.getFullModList")
    except Exception as e:
        print(f"Error fetching mod list for endorsed mods: {e}")
        return {"endorsed_ids": []}

    endorsed_ids: List[int] = []
    if mods:
        for mod in mods:
            try:
                nid = mod.get("nexus_id")
                is_endorsed = bool(mod.get("is_endorsed"))
                if is_endorsed and nid:
                    endorsed_ids.append(nid)
            except Exception as e:
                print(f"Error reading endorsed Nexus ID from {mod}: {e}")

    return {"endorsed_ids": endorsed_ids}