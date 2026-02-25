import mobase  # pyright: ignore[reportMissingImports]
import threading
from .more_informative_nexus_requirements_server import run as run_server
from .bridge_client import MO2BridgeClient

class MoreInformativeNexusRequirementsPlugin(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self._server_thread = None
        self._organizer = None

    def init(self, organizer):
        self._organizer = organizer

        try:
            client = MO2BridgeClient(host="127.0.0.1", port=52525, name="MoreInformativeNexusRequirements")
            if not client.connect():
                return False
            self._server_thread = threading.Thread(
                target=run_server,
                kwargs={"client": client},
                daemon=True,
            )
            self._server_thread.start()

            return True

        except Exception:
            return False
    
    def name(self):
        return "MoreInformativeNexusRequirements"
    
    def author(self):
        return "feelo496"
    
    def description(self):
        return "Provides a more informative requirements tab"
    
    def version(self):
        return mobase.VersionInfo(1, 0, 0)
    
    def isActive(self):
        return True
    
    def settings(self):
        return []

def createPlugin():
    return MoreInformativeNexusRequirementsPlugin()