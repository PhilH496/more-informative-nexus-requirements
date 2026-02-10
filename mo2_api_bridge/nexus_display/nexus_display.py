import time
from typing import Dict, List
from bridge_client import MO2BridgeClient

def getModIds(client: MO2BridgeClient) -> Dict[str, List[int]]:
    mod_names = client.call('modList.allMods')
    nexus_ids = []

    if mod_names:
        for mod_name in mod_names:
            try:
                nexus_id = client.call('modList.nexusId', mod_name)
                if nexus_id:
                    nexus_ids.append(nexus_id)
            except Exception as e:
                print(f'Error getting Nexus ID for {mod_name}: {e}')
    return {'nexus_ids': nexus_ids}