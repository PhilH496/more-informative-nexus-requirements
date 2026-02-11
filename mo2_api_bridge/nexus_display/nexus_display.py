from typing import Dict, List
from bridge_client import MO2BridgeClient

def getModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets all mod ids."""
    mod_names = client.call('modList.allMods')
    nexus_ids = []

    if mod_names:
        for mod_name in mod_names:
            try:
                nexus_id = client.call('modList.nexusId', mod_name)
                if nexus_id and nexus_id != -1:
                    nexus_ids.append(nexus_id)
            except Exception as e:
                print(f'Error getting Nexus ID for {mod_name}: {e}')
    return {'nexus_ids': nexus_ids}

def getEnabledModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    """Gets only enabled mod ids."""
    mod_names = client.call('modList.allMods')

    enabled_ids = []
    if mod_names:
        for mod_name in mod_names:
            try:
                state = client.call('modList.state', mod_name)
                if state == 35: # 35 is the state for enabled mods
                    nexus_id = client.call('modList.nexusId', mod_name)
                    if nexus_id and nexus_id != -1:
                        enabled_ids.append(nexus_id)

            except Exception as e:
                print(f'Error getting enabled mod id for {mod_name}: {e}')
    return {'enabled_ids': enabled_ids}