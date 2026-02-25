# -*- coding: utf-8 -*-
"""
MO2 AI Bridge Plugin - BATCH API VERSION
==========================================
Added batch methods for high-performance operations.

Author: AI Bridge Team
Version: 1.4.0
==========================================
original code by AlhimikPh on nexusmods.com
"""

import mobase
import json
import socket
import threading
import subprocess
import sys
import os
import uuid
import time
import traceback
import weakref
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

# PyQt6 imports
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QObject, QCoreApplication
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QTabWidget, QWidget
)
from PyQt6.QtGui import QIcon


# =============================================================================
# SECTION 1: MESSAGE PROTOCOL & DATA STRUCTURES
# =============================================================================

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HANDSHAKE = "handshake"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class EventType(Enum):
    MOD_LIST_CHANGED = "mod_list_changed"
    PROFILE_CHANGED = "profile_changed"
    PLUGIN_STATE_CHANGED = "plugin_state_changed"
    FILE_RENAMED = "file_renamed"
    FILE_MOVED = "file_moved"
    REFRESH_STARTED = "refresh_started"
    REFRESH_COMPLETED = "refresh_completed"
    PROFILE_RENAMED = "profile_renamed"
    PROFILE_REMOVED = "profile_removed"
    PROFILE_CREATED = "profile_created"
    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_COMPLETED = "download_completed"
    INSTALLATION_STARTED = "installation_started"
    INSTALLATION_COMPLETED = "installation_completed"
    USER_INTERFACE_INITIALIZED = "ui_initialized"
    ABOUT_TO_RUN = "about_to_run"
    FINISHED_RUN = "finished_run"
    CLIENT_CONNECTED = "client_connected"
    CLIENT_DISCONNECTED = "client_disconnected"
    BRIDGE_STARTED = "bridge_started"
    BRIDGE_STOPPED = "bridge_stopped"
    EXTERNAL_PLUGIN_STARTED = "external_plugin_started"
    EXTERNAL_PLUGIN_CRASHED = "external_plugin_crashed"


@dataclass
class BridgeMessage:
    type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: Optional[str] = None
    method: Optional[str] = None
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    event_type: Optional[str] = None
    event_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BridgeMessage':
        return cls(**json.loads(json_str))
    
    @classmethod
    def create_request(cls, method: str, args: List = None, 
                       kwargs: Dict = None, client_id: str = None) -> 'BridgeMessage':
        return cls(
            type=MessageType.REQUEST.value,
            method=method,
            args=args or [],
            kwargs=kwargs or {},
            client_id=client_id
        )
    
    @classmethod
    def create_response(cls, request_id: str, result: Any = None,
                        error: str = None, traceback_str: str = None) -> 'BridgeMessage':
        return cls(
            type=MessageType.RESPONSE.value,
            id=request_id,
            result=result,
            error=error,
            error_traceback=traceback_str
        )
    
    @classmethod
    def create_event(cls, event_type: EventType, data: Dict = None) -> 'BridgeMessage':
        return cls(
            type=MessageType.EVENT.value,
            event_type=event_type.value,
            event_data=data or {}
        )


# =============================================================================
# SECTION 2: EVENT POOL
# =============================================================================

class EventPool:
    """Pool of reusable threading.Event objects."""
    
    def __init__(self, initial_size: int = 10, max_size: int = 50):
        self._pool: deque = deque()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._created_count = 0
        
        for _ in range(initial_size):
            self._pool.append(threading.Event())
            self._created_count += 1
    
    def acquire(self) -> threading.Event:
        with self._lock:
            if self._pool:
                event = self._pool.popleft()
                event.clear()
                return event
            
            if self._created_count < self._max_size:
                self._created_count += 1
                return threading.Event()
        
        return threading.Event()
    
    def release(self, event: threading.Event) -> None:
        with self._lock:
            if len(self._pool) < self._max_size:
                event.clear()
                self._pool.append(event)
    
    def clear(self) -> None:
        with self._lock:
            self._pool.clear()


_event_pool = EventPool(initial_size=5, max_size=20)


# =============================================================================
# SECTION 3: THREAD-SAFE API EXECUTOR WITH BATCH SUPPORT
# =============================================================================

@dataclass
class PendingRequest:
    method: str
    args: List[Any]
    kwargs: Dict[str, Any]
    completion_event: threading.Event
    result: Any = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    completed: bool = False


class APIExecutor(QObject):
    """
    Executes API calls in the main Qt thread.
    Now includes batch operations for high performance.
    """
    
    _execute_signal = pyqtSignal(str)
    
    MAX_PENDING_REQUESTS = 100
    REQUEST_TIMEOUT = 30.0
    
    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._interfaces: Dict[str, Any] = {}
        self._methods: Dict[str, Dict] = {}
        self._batch_methods: Dict[str, callable] = {}
        
        self._pending: Dict[str, PendingRequest] = {}
        self._lock = threading.RLock()
        self._cleanup_counter = 0
        
        self._execute_signal.connect(
            self._do_execute_in_main_thread, 
            Qt.ConnectionType.QueuedConnection
        )
        
        self._build_interfaces()
        self._generate_methods()
        self._register_batch_methods()
    
    def _build_interfaces(self) -> None:
        self._interfaces = {"organizer": self._organizer}
        
        for name, getter in [
            ("modList", lambda: self._organizer.modList()),
            ("pluginList", lambda: self._organizer.pluginList()),
            ("downloadManager", lambda: self._organizer.downloadManager()),
            ("profile", lambda: self._organizer.profile()),
        ]:
            try:
                self._interfaces[name] = getter()
            except Exception as e:
                print(f"[Bridge] Warning: {name}: {e}")
    
    # def _generate_methods(self) -> None:
        # """Generate standard method registry."""
        # methods = [
            # # Organizer
            # "organizer.modList", "organizer.pluginList", "organizer.downloadManager",
            # "organizer.profile", "organizer.profileName", "organizer.profilePath",
            # "organizer.modsPath", "organizer.downloadsPath", "organizer.overwritePath",
            # "organizer.basePath", "organizer.managedGame", "organizer.refreshModList",
            # "organizer.resolvePath", "organizer.findFiles",
            # # ModList
            # "modList.allMods", "modList.state", "modList.setActive",
            # "modList.priority", "modList.setPriority", "modList.displayName",
            # # PluginList
            # "pluginList.pluginNames", "pluginList.state", "pluginList.setState",
            # "pluginList.priority", "pluginList.loadOrder",
            # # Profile
            # "profile.name", "profile.absolutePath",
            # # ===== BATCH METHODS =====
            # "batch.getFullModList",
            # "batch.getModsInfo",
            # "batch.getFullPluginList",
            # "batch.getPluginsInfo",
            # "batch.setModsActive",
            # "batch.setModsPriority",
            # "batch.setPluginsState",
            # "batch.execute",
            # "batch.resolveMultiplePaths",
        # ]
        # self._methods = {m: {"path": m} for m in methods}
        
    def _generate_methods(self) -> None:
        """Generate method registry from mobase_api.json instead of fixed list."""
        methods = []

        api_json_path = Path(__file__).parent / "mobase_api.json"
        print(f"[Bridge] Looking for API JSON at {api_json_path}")

        if api_json_path.exists():
            try:
                with open(api_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                print(f"[Bridge] JSON keys: {list(data.keys())}")

                # --- interfaces ---
                interfaces = data.get("interfaces", {})
                for iface_name, iface_data in interfaces.items():
                    iface_methods = iface_data.get("methods", {})
                    for mname in iface_methods.keys():
                        full_name = f"{iface_name}.{mname}"
                        methods.append(full_name)
                        print(f"[Bridge] Interface method: {full_name}")

                # --- classes ---
                classes = data.get("classes", {})
                for class_name, class_data in classes.items():
                    class_methods = class_data.get("methods", {})
                    for mname in class_methods.keys():
                        full_name = f"{class_name}.{mname}"
                        methods.append(full_name)
                        print(f"[Bridge] Class method: {full_name}")

            except Exception as e:
                print(f"[Bridge] Failed to parse mobase_api.json: {e}")

        if not methods:
            # fallback на фиксированный список
            methods = [
                "organizer.modList", "organizer.pluginList", "organizer.downloadManager",
                "organizer.profile", "organizer.profileName", "organizer.profilePath",
                "organizer.modsPath", "organizer.downloadsPath", "organizer.overwritePath",
                "organizer.basePath", "organizer.managedGame", "organizer.refreshModList",
                "organizer.resolvePath", "organizer.findFiles",
                "modList.allMods", "modList.state", "modList.setActive",
                "modList.priority", "modList.setPriority", "modList.displayName",
                "pluginList.pluginNames", "pluginList.state", "pluginList.setState",
                "pluginList.priority", "pluginList.loadOrder",
                "profile.name", "profile.absolutePath",
                # batch methods
                "batch.getFullModList", "batch.getModsInfo",
                "batch.getFullPluginList", "batch.getPluginsInfo",
                "batch.setModsActive", "batch.setModsPriority",
                "batch.setPluginsState", "batch.execute",
                "batch.resolveMultiplePaths",
            ]

        self._methods = {m: {"path": m} for m in methods}
        print(f"[Bridge] Registered {len(methods)} methods")

        
    
    def _register_batch_methods(self) -> None:
        """Register batch method implementations."""
        self._batch_methods = {
            "batch.getFullModList": self._batch_get_full_mod_list,
            "batch.getModsInfo": self._batch_get_mods_info,
            "batch.getFullPluginList": self._batch_get_full_plugin_list,
            "batch.getPluginsInfo": self._batch_get_plugins_info,
            "batch.setModsActive": self._batch_set_mods_active,
            "batch.setModsPriority": self._batch_set_mods_priority,
            "batch.setPluginsState": self._batch_set_plugins_state,
            "batch.execute": self._batch_execute,
            "batch.resolveMultiplePaths": self._batch_resolve_multiple_paths,
        }
    
    # =========================================================================
    # BATCH METHOD IMPLEMENTATIONS
    # =========================================================================
    
    def _batch_get_full_mod_list(self, args: List, kwargs: Dict) -> List[Dict]:
        """
        Get all mods with their states and priorities in ONE call.
        Returns: [{name, state, priority, display_name}, ...]
        
        ~20x faster than individual calls for 150+ mods.
        """
        modlist = self._interfaces.get("modList") or self._organizer.modList()
        result = []
        
        for mod in modlist.allMods():
            try:
                state = modlist.state(mod)
                state_value = state.value if hasattr(state, 'value') else int(state)
                
                result.append({
                    "name": mod,
                    "state": state_value,
                    "state_text": {0: "missing", 1: "disabled", 2: "enabled"}.get(state_value, "unknown"),
                    "priority": modlist.priority(mod),
                    "display_name": modlist.displayName(mod) or mod
                })
            except Exception as e:
                result.append({
                    "name": mod,
                    "error": str(e)
                })
        
        return result
    
    def _batch_get_mods_info(self, args: List, kwargs: Dict) -> List[Dict]:
        """
        Get info for specific mods.
        Args: [mod_names] - list of mod names
        Returns: [{name, state, priority, display_name}, ...]
        """
        mod_names = args[0] if args else kwargs.get("mod_names", [])
        modlist = self._interfaces.get("modList") or self._organizer.modList()
        result = []
        
        for mod in mod_names:
            try:
                state = modlist.state(mod)
                state_value = state.value if hasattr(state, 'value') else int(state)
                
                result.append({
                    "name": mod,
                    "state": state_value,
                    "state_text": {0: "missing", 1: "disabled", 2: "enabled"}.get(state_value, "unknown"),
                    "priority": modlist.priority(mod),
                    "display_name": modlist.displayName(mod) or mod,
                    "success": True
                })
            except Exception as e:
                result.append({
                    "name": mod,
                    "success": False,
                    "error": str(e)
                })
        
        return result
    
    def _batch_get_full_plugin_list(self, args: List, kwargs: Dict) -> List[Dict]:
        """
        Get all plugins with states and load order in ONE call.
        Returns: [{name, state, priority, load_order}, ...]
        """
        pluginlist = self._interfaces.get("pluginList") or self._organizer.pluginList()
        result = []
        
        for plugin in pluginlist.pluginNames():
            try:
                state = pluginlist.state(plugin)
                state_value = state.value if hasattr(state, 'value') else int(state)
                
                result.append({
                    "name": plugin,
                    "state": state_value,
                    "state_text": {0: "missing", 1: "disabled", 2: "enabled"}.get(state_value, "unknown"),
                    "priority": pluginlist.priority(plugin),
                    "load_order": pluginlist.loadOrder(plugin)
                })
            except Exception as e:
                result.append({
                    "name": plugin,
                    "error": str(e)
                })
        
        return result
    
    def _batch_get_plugins_info(self, args: List, kwargs: Dict) -> List[Dict]:
        """
        Get info for specific plugins.
        Args: [plugin_names] - list of plugin names
        """
        plugin_names = args[0] if args else kwargs.get("plugin_names", [])
        pluginlist = self._interfaces.get("pluginList") or self._organizer.pluginList()
        result = []
        
        for plugin in plugin_names:
            try:
                state = pluginlist.state(plugin)
                state_value = state.value if hasattr(state, 'value') else int(state)
                
                result.append({
                    "name": plugin,
                    "state": state_value,
                    "priority": pluginlist.priority(plugin),
                    "load_order": pluginlist.loadOrder(plugin),
                    "success": True
                })
            except Exception as e:
                result.append({
                    "name": plugin,
                    "success": False,
                    "error": str(e)
                })
        
        return result
    
    def _batch_set_mods_active(self, args: List, kwargs: Dict) -> Dict:
        """
        Enable/disable multiple mods in ONE call.
        Args: [mods_dict] where mods_dict = {"ModName": true/false, ...}
        OR Args: [mod_names, active] to set all to same state
        
        Returns: {success: bool, results: [{name, success, error?}, ...]}
        """
        modlist = self._interfaces.get("modList") or self._organizer.modList()
        results = []
        
        if len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], bool):
            # Format: [["Mod1", "Mod2"], true]
            mod_names = args[0]
            active = args[1]
            mods_dict = {name: active for name in mod_names}
        elif args and isinstance(args[0], dict):
            # Format: [{"Mod1": true, "Mod2": false}]
            mods_dict = args[0]
        else:
            mods_dict = kwargs.get("mods", {})
        
        for mod_name, active in mods_dict.items():
            try:
                modlist.setActive(mod_name, bool(active))
                results.append({"name": mod_name, "success": True, "active": active})
            except Exception as e:
                results.append({"name": mod_name, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count == len(results),
            "total": len(results),
            "succeeded": success_count,
            "failed": len(results) - success_count,
            "results": results
        }
    
    def _batch_set_mods_priority(self, args: List, kwargs: Dict) -> Dict:
        """
        Set priority for multiple mods in ONE call.
        Args: [priorities_dict] where priorities_dict = {"ModName": priority, ...}
        
        Returns: {success: bool, results: [{name, success, old_priority, new_priority}, ...]}
        """
        modlist = self._interfaces.get("modList") or self._organizer.modList()
        results = []
        
        priorities_dict = args[0] if args and isinstance(args[0], dict) else kwargs.get("priorities", {})
        
        for mod_name, priority in priorities_dict.items():
            try:
                old_priority = modlist.priority(mod_name)
                modlist.setPriority(mod_name, int(priority))
                new_priority = modlist.priority(mod_name)
                results.append({
                    "name": mod_name,
                    "success": True,
                    "old_priority": old_priority,
                    "new_priority": new_priority
                })
            except Exception as e:
                results.append({"name": mod_name, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count == len(results),
            "total": len(results),
            "succeeded": success_count,
            "results": results
        }
    
    def _batch_set_plugins_state(self, args: List, kwargs: Dict) -> Dict:
        """
        Set state for multiple plugins in ONE call.
        Args: [states_dict] where states_dict = {"Plugin.esp": state, ...}
        States: 1 = disabled, 2 = enabled
        
        Returns: {success: bool, results: [...]}
        """
        pluginlist = self._interfaces.get("pluginList") or self._organizer.pluginList()
        results = []
        
        if len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], int):
            # Format: [["Plugin1.esp", "Plugin2.esp"], 2]
            plugin_names = args[0]
            state = args[1]
            states_dict = {name: state for name in plugin_names}
        elif args and isinstance(args[0], dict):
            states_dict = args[0]
        else:
            states_dict = kwargs.get("plugins", {})
        
        for plugin_name, state in states_dict.items():
            try:
                pluginlist.setState(plugin_name, int(state))
                results.append({"name": plugin_name, "success": True, "state": state})
            except Exception as e:
                results.append({"name": plugin_name, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count == len(results),
            "total": len(results),
            "succeeded": success_count,
            "results": results
        }
    
    def _batch_execute(self, args: List, kwargs: Dict) -> List[Dict]:
        """
        Execute multiple arbitrary API calls in ONE request.
        Args: [calls] where calls = [{"method": "...", "args": [...]}, ...]
        
        Returns: [{success, method, result?, error?}, ...]
        
        Example:
            batch.execute([
                {"method": "modList.state", "args": ["Mod1"]},
                {"method": "modList.state", "args": ["Mod2"]},
                {"method": "modList.priority", "args": ["Mod1"]}
            ])
        """
        calls = args[0] if args else kwargs.get("calls", [])
        results = []
        
        for call in calls:
            method = call.get("method", "")
            call_args = call.get("args", [])
            call_kwargs = call.get("kwargs", {})
            
            try:
                result = self._invoke_method(method, call_args, call_kwargs)
                results.append({
                    "success": True,
                    "method": method,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "method": method,
                    "error": str(e)
                })
        
        return results
    
    def _batch_resolve_multiple_paths(self, args: List, kwargs: Dict) -> Dict[str, str]:
        """
        Resolve multiple virtual paths in ONE call.
        Args: [paths] - list of virtual paths
        
        Returns: {"virtual_path": "real_path", ...}
        
        Useful for conflict detection.
        """
        paths = args[0] if args else kwargs.get("paths", [])
        results = {}
        
        for path in paths:
            try:
                resolved = self._organizer.resolvePath(path)
                results[path] = str(resolved) if resolved else None
            except Exception as e:
                results[path] = None
        
        return results
    
    
    
    
    
    # =========================================================================
    # CORE EXECUTION
    # =========================================================================
    
    def get_all_methods(self) -> Dict[str, Dict]:
        return self._methods.copy()
    
    def _is_main_thread(self) -> bool:
        app = QCoreApplication.instance()
        if app is None:
            return True
        return QThread.currentThread() == app.thread()
    
    def _cleanup_stale_requests(self) -> None:
        self._cleanup_counter += 1
        if self._cleanup_counter < 10:
            return
        
        self._cleanup_counter = 0
        
        with self._lock:
            stale_ids = []
            for req_id, req in self._pending.items():
                if req.completed:
                    stale_ids.append(req_id)
            
            for req_id in stale_ids[:10]:
                pending = self._pending.pop(req_id, None)
                if pending and pending.completion_event:
                    _event_pool.release(pending.completion_event)
    
    def execute(self, method_path: str, args: List = None,
                kwargs: Dict = None, timeout: float = None) -> Any:
        args = args or []
        kwargs = kwargs or {}
        timeout = timeout or self.REQUEST_TIMEOUT
        
        self._cleanup_stale_requests()
        
        if self._is_main_thread():
            return self._invoke_method(method_path, args, kwargs)
        
        with self._lock:
            if len(self._pending) >= self.MAX_PENDING_REQUESTS:
                raise RuntimeError("Too many pending API requests")
            
            request_id = str(uuid.uuid4())
            completion_event = _event_pool.acquire()
            
            pending = PendingRequest(
                method=method_path,
                args=args,
                kwargs=kwargs,
                completion_event=completion_event
            )
            self._pending[request_id] = pending
        
        try:
            self._execute_signal.emit(request_id)
            
            if not completion_event.wait(timeout=timeout):
                with self._lock:
                    if request_id in self._pending:
                        self._pending[request_id].completed = True
                raise TimeoutError(f"API call timed out after {timeout}s: {method_path}")
            
            with self._lock:
                pending = self._pending.get(request_id)
                if not pending:
                    raise RuntimeError("Request disappeared")
                
                if pending.error:
                    raise RuntimeError(f"API error: {pending.error}")
                
                return pending.result
        
        finally:
            with self._lock:
                pending = self._pending.pop(request_id, None)
                if pending and pending.completion_event:
                    _event_pool.release(pending.completion_event)
    
    @pyqtSlot(str)
    def _do_execute_in_main_thread(self, request_id: str) -> None:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None or pending.completed:
                return
            
            method_path = pending.method
            args = pending.args
            kwargs = pending.kwargs
        
        result = None
        error = None
        tb = None
        
        try:
            result = self._invoke_method(method_path, args, kwargs)
        except Exception as e:
            error = str(e)
            tb = traceback.format_exc()
        
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is not None:
                pending.result = result
                pending.error = error
                pending.traceback = tb
                pending.completed = True
                pending.completion_event.set()
    
    def _invoke_method(self, method_path: str, args: List, kwargs: Dict) -> Any:
        # Check if it's a batch method
        if method_path in self._batch_methods:
            return self._batch_methods[method_path](args, kwargs)
        
        parts = method_path.split('.')
        
        if len(parts) == 2:
            interface_name, method_name = parts
        elif len(parts) == 1:
            interface_name, method_name = "organizer", parts[0]
        else:
            raise ValueError(f"Invalid method path: {method_path}")
        
        if interface_name == "profile":
            try:
                self._interfaces["profile"] = self._organizer.profile()
            except Exception:
                pass
        
        interface = self._interfaces.get(interface_name)
        if interface is None:
            if hasattr(self._organizer, interface_name):
                attr = getattr(self._organizer, interface_name)
                interface = attr() if callable(attr) else attr
                self._interfaces[interface_name] = interface
            else:
                raise ValueError(f"Unknown interface: {interface_name}")

        # janky way to get nexusId from modList
        if interface_name == "modList" and method_name == "nexusId":
            mod_name = args[0]
            mod_interface = self._organizer.getMod(mod_name)
            result = mod_interface.nexusId()
            return self._serialize_result(result)
        
        if not hasattr(interface, method_name):
            raise ValueError(f"Method '{method_name}' not found on {interface_name}")
        
        method = getattr(interface, method_name)
        result = method(*args, **kwargs) if callable(method) else method
        
        return self._serialize_result(result)
    
    def _serialize_result(self, result: Any) -> Any:
        if result is None or isinstance(result, (str, int, float, bool)):
            return result
        
        if isinstance(result, (list, tuple)):
            return [self._serialize_result(item) for item in result]
        
        if isinstance(result, dict):
            return {str(k): self._serialize_result(v) for k, v in result.items()}
        
        if isinstance(result, Path):
            return str(result)
        
        if hasattr(result, 'name'):
            try:
                name = result.name
                name_value = name() if callable(name) else name
                return {"__type__": type(result).__name__, "name": str(name_value)}
            except Exception:
                pass
        
        if isinstance(result, Enum):
            return {"__type__": "enum", "name": result.name, "value": result.value}
        
        try:
            return str(result)
        except Exception:
            return f"<{type(result).__name__}>"
    
    def refresh_interfaces(self) -> None:
        self._build_interfaces()
    
    def cleanup(self) -> None:
        with self._lock:
            for req_id, pending in list(self._pending.items()):
                pending.completed = True
                if pending.completion_event:
                    pending.completion_event.set()
                    _event_pool.release(pending.completion_event)
            self._pending.clear()


# =============================================================================
# SECTION 4: CONNECTED CLIENT DATA
# =============================================================================

@dataclass
class ConnectedClient:
    id: str
    socket: socket.socket
    address: tuple
    name: str = "Unknown"
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    subscribed_events: Set[str] = field(default_factory=set)
    is_alive: bool = True
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update_activity(self) -> None:
        self.last_activity = time.time()


# =============================================================================
# SECTION 5: TCP IPC SERVER
# =============================================================================

class IPCServer(QThread):
    """TCP-based IPC server."""
    
    client_connected = pyqtSignal(str, str)
    client_disconnected = pyqtSignal(str)
    message_received = pyqtSignal(str, str)
    message_sent = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)
    server_started = pyqtSignal(int)
    server_stopped = pyqtSignal()
    
    DEFAULT_PORT = 52525
    BUFFER_SIZE = 65536
    MAX_BUFFER_SIZE = 1024 * 1024
    MESSAGE_DELIMITER = b'\n\x00\x00\n'
    HEARTBEAT_INTERVAL = 30.0
    CLIENT_TIMEOUT = 5.0
    MAX_CLIENTS = 10
    
    def __init__(self, api_executor: APIExecutor, parent=None):
        super().__init__(parent)
        self._api_executor = api_executor
        
        self._clients: Dict[str, ConnectedClient] = {}
        self._clients_lock = threading.RLock()
        self._server_socket: Optional[socket.socket] = None
        self._stop_event = threading.Event()
        self._port = self.DEFAULT_PORT
        self._client_threads: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    
    @property
    def port(self) -> int:
        return self._port
    
    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set() and self.isRunning()
    
    @property
    def connected_clients(self) -> Dict[str, ConnectedClient]:
        with self._clients_lock:
            return {k: v for k, v in self._clients.items()}
    
    def run(self) -> None:
        try:
            self._start_server()
            self._accept_loop()
        except Exception as e:
            if not self._stop_event.is_set():
                self.error_occurred.emit(f"Server error: {e}")
        finally:
            self._cleanup()
    
    def _start_server(self) -> None:
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        for port_offset in range(10):
            try:
                self._port = self.DEFAULT_PORT + port_offset
                self._server_socket.bind(('127.0.0.1', self._port))
                break
            except OSError:
                if port_offset == 9:
                    raise RuntimeError("No available port")
        
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        self.server_started.emit(self._port)
        print(f"[Bridge] Server started on port {self._port}")
    
    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._clients_lock:
                    if len(self._clients) >= self.MAX_CLIENTS:
                        time.sleep(0.5)
                        continue
                
                client_socket, address = self._server_socket.accept()
                client_id = str(uuid.uuid4())[:16]
                
                client = ConnectedClient(
                    id=client_id,
                    socket=client_socket,
                    address=address
                )
                
                with self._clients_lock:
                    self._clients[client_id] = client
                
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                    name=f"Client-{client_id[:8]}"
                )
                handler.start()
                self._client_threads[client_id] = handler
                
                self.client_connected.emit(client_id, f"{address[0]}:{address[1]}")
                
            except socket.timeout:
                continue
            except OSError:
                if not self._stop_event.is_set():
                    raise
                break
    
    def _handle_client(self, client: ConnectedClient) -> None:
        buffer = b""
        last_heartbeat = time.time()
        
        try:
            # Include batch methods in handshake
            # Include batch methods in handshake
            all_methods = list(self._api_executor.get_all_methods().keys())
            available = all_methods  # или фильтруй, если нужно только batch.*

            handshake = BridgeMessage(
                type=MessageType.HANDSHAKE.value,
                client_id=client.id,
                result={
                    "client_id": client.id,
                    "server_version": "1.4.0",
                    "available_methods": available,
                    "available_events": [e.value for e in EventType]
                }
            )
            
            if not self._send_to_client(client, handshake):
                return
            
            client.socket.settimeout(self.CLIENT_TIMEOUT)
            
            while client.is_alive and not self._stop_event.is_set():
                try:
                    data = client.socket.recv(self.BUFFER_SIZE)
                    
                    if not data:
                        break
                    
                    buffer += data
                    client.update_activity()
                    
                    while self.MESSAGE_DELIMITER in buffer:
                        msg_data, buffer = buffer.split(self.MESSAGE_DELIMITER, 1)
                        try:
                            self._process_message(client, msg_data.decode('utf-8'))
                        except Exception as e:
                            print(f"[Bridge] Message error: {e}")
                    
                    if len(buffer) > self.MAX_BUFFER_SIZE:
                        buffer = b""
                    
                except socket.timeout:
                    now = time.time()
                    if now - last_heartbeat > self.HEARTBEAT_INTERVAL:
                        heartbeat = BridgeMessage(type=MessageType.HEARTBEAT.value)
                        if not self._send_to_client(client, heartbeat):
                            break
                        last_heartbeat = now
                        
                except (ConnectionResetError, ConnectionAbortedError):
                    break
                except Exception as e:
                    if client.is_alive:
                        print(f"[Bridge] Client error: {e}")
                    break
                    
        finally:
            self._disconnect_client(client.id)
    
    def _process_message(self, client: ConnectedClient, msg_json: str) -> None:
        self.message_received.emit(client.id, msg_json[:100])
        
        try:
            message = BridgeMessage.from_json(msg_json)
        except json.JSONDecodeError as e:
            error_response = BridgeMessage.create_response("unknown", error=f"Invalid JSON: {e}")
            self._send_to_client(client, error_response)
            return
        
        message.client_id = client.id
        
        if message.type == MessageType.REQUEST.value:
            self._handle_request(client, message)
        elif message.type == MessageType.HANDSHAKE.value:
            self._handle_client_handshake(client, message)
        elif message.type == MessageType.HEARTBEAT.value:
            client.update_activity()
    
    def _handle_request(self, client: ConnectedClient, message: BridgeMessage) -> None:
        try:
            result = self._api_executor.execute(
                message.method,
                message.args,
                message.kwargs
            )
            response = BridgeMessage.create_response(message.id, result=result)
        except Exception as e:
            response = BridgeMessage.create_response(
                message.id, error=str(e), traceback_str=traceback.format_exc()
            )
        
        self._send_to_client(client, response)
    
    def _handle_client_handshake(self, client: ConnectedClient, message: BridgeMessage) -> None:
        if message.kwargs:
            client.name = message.kwargs.get("name", "Unknown")
            events = message.kwargs.get("subscribe_events", [])
            client.subscribed_events = set(events) if events else set()
    
    def _send_to_client(self, client: ConnectedClient, message: BridgeMessage) -> bool:
        if not client.is_alive:
            return False
        
        try:
            data = message.to_json().encode('utf-8') + self.MESSAGE_DELIMITER
            
            with client.send_lock:
                client.socket.sendall(data)
            
            return True
        except Exception:
            client.is_alive = False
            return False
    
    def broadcast_event(self, event: BridgeMessage, exclude_client: str = None) -> None:
        with self._clients_lock:
            clients_copy = list(self._clients.items())
        
        for client_id, client in clients_copy:
            if client_id == exclude_client or not client.is_alive:
                continue
            
            if client.subscribed_events:
                if event.event_type not in client.subscribed_events and "*" not in client.subscribed_events:
                    continue
            
            try:
                self._send_to_client(client, event)
            except Exception:
                pass
    
    def _disconnect_client(self, client_id: str) -> None:
        with self._clients_lock:
            client = self._clients.pop(client_id, None)
        
        if client:
            client.is_alive = False
            try:
                client.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                client.socket.close()
            except Exception:
                pass
            
            self.client_disconnected.emit(client_id)
    
    def stop(self) -> None:
        print("[Bridge] Stopping server...")
        self._stop_event.set()
        
        with self._clients_lock:
            client_ids = list(self._clients.keys())
        
        for client_id in client_ids:
            self._disconnect_client(client_id)
        
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        
        if self.isRunning():
            self.wait(3000)
        
        self.server_stopped.emit()
    
    def _cleanup(self) -> None:
        self._stop_event.set()
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None


# =============================================================================
# SECTION 6: EXTERNAL PLUGINS MANAGER
# =============================================================================

class ExternalPluginManager(QObject):
    """Manages external plugins."""
    
    plugin_started = pyqtSignal(str, int)
    plugin_crashed = pyqtSignal(str, str)
    plugin_output = pyqtSignal(str, str)
    
    MAX_PLUGINS = 5
    
    def __init__(self, plugins_folder: Path, server_port: int, parent=None):
        super().__init__(parent)
        self._plugins_folder = plugins_folder
        self._server_port = server_port
        self._processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
    
    @property
    def server_port(self) -> int:
        return self._server_port
    
    @server_port.setter
    def server_port(self, value: int) -> None:
        self._server_port = value
    
    def start_all_plugins(self) -> None:
        if not self._plugins_folder.exists():
            self._plugins_folder.mkdir(parents=True, exist_ok=True)
            return
        
        count = 0
        for plugin_file in self._plugins_folder.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            if count >= self.MAX_PLUGINS:
                break
            if self.start_plugin(plugin_file):
                count += 1
    
    def start_plugin(self, plugin_path: Path) -> bool:
        plugin_name = plugin_path.stem
        
        with self._lock:
            if plugin_name in self._processes:
                if self._processes[plugin_name].poll() is None:
                    return False
        
        try:
            env = os.environ.copy()
            env['MO2_BRIDGE_PORT'] = str(self._server_port)
            env['MO2_BRIDGE_HOST'] = '127.0.0.1'
            env['MO2_PLUGIN_NAME'] = plugin_name
            
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                [sys.executable, str(plugin_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(plugin_path.parent),
                creationflags=creationflags
            )
            
            with self._lock:
                self._processes[plugin_name] = process
            
            self.plugin_started.emit(plugin_name, process.pid)
            
            monitor = threading.Thread(
                target=self._monitor_plugin,
                args=(plugin_name, process),
                daemon=True
            )
            monitor.start()
            
            return True
            
        except Exception as e:
            self.plugin_crashed.emit(plugin_name, str(e))
            return False
    
    def _monitor_plugin(self, name: str, process: subprocess.Popen) -> None:
        try:
            stdout, stderr = process.communicate(timeout=None)
            
            return_code = process.returncode
            if return_code != 0 and not self._stop_event.is_set():
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else ""
                self.plugin_crashed.emit(name, f"Exit {return_code}: {error_msg[:500]}")
                    
        except Exception as e:
            if not self._stop_event.is_set():
                self.plugin_crashed.emit(name, str(e))
        finally:
            with self._lock:
                self._processes.pop(name, None)
    
    def stop_plugin(self, plugin_name: str) -> None:
        with self._lock:
            process = self._processes.get(plugin_name)
        
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass
        
        with self._lock:
            self._processes.pop(plugin_name, None)
    
    def stop_all_plugins(self) -> None:
        self._stop_event.set()
        
        with self._lock:
            names = list(self._processes.keys())
        
        for name in names:
            self.stop_plugin(name)
    
    @property
    def running_plugins(self) -> Dict[str, int]:
        with self._lock:
            return {n: p.pid for n, p in self._processes.items() if p.poll() is None}


# =============================================================================
# SECTION 7: MO2 EVENT HANDLERS
# =============================================================================

class MO2EventHandler(QObject):
    """Connects to MO2 signals."""
    
    event_triggered = pyqtSignal(object)
    
    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        try:
            modlist = self._organizer.modList()
            modlist.onModInstalled(self._on_mod_installed)
            modlist.onModRemoved(self._on_mod_removed)
            modlist.onModStateChanged(self._on_mod_state_changed)
        except Exception as e:
            print(f"[Bridge] ModList signals error: {e}")
        
        try:
            pluginlist = self._organizer.pluginList()
            pluginlist.onPluginStateChanged(self._on_plugin_state_changed)
        except Exception as e:
            print(f"[Bridge] PluginList signals error: {e}")
        
        try:
            self._organizer.onProfileChanged(self._on_profile_changed)
        except Exception as e:
            print(f"[Bridge] Profile signals error: {e}")
    
    def _emit_event(self, event_type: EventType, data: Dict = None) -> None:
        event = BridgeMessage.create_event(event_type, data or {})
        self.event_triggered.emit(event)
    
    def _safe_value(self, val: Any) -> Any:
        if isinstance(val, int):
            return val
        if hasattr(val, 'value'):
            return int(val.value)
        try:
            return int(val)
        except:
            return str(val)
    
    def _on_mod_installed(self, mod_name: str) -> None:
        self._emit_event(EventType.MOD_LIST_CHANGED, {"action": "installed", "mod": str(mod_name)})
    
    def _on_mod_removed(self, mod_name: str) -> None:
        self._emit_event(EventType.MOD_LIST_CHANGED, {"action": "removed", "mod": str(mod_name)})
    
    def _on_mod_state_changed(self, states: Dict) -> None:
        try:
            states_dict = {str(k): self._safe_value(v) for k, v in states.items()}
        except:
            states_dict = {}
        self._emit_event(EventType.MOD_LIST_CHANGED, {"action": "state_changed", "states": states_dict})
    
    def _on_plugin_state_changed(self, states: Dict) -> None:
        try:
            states_dict = {str(k): self._safe_value(v) for k, v in states.items()}
        except:
            states_dict = {}
        self._emit_event(EventType.PLUGIN_STATE_CHANGED, {"states": states_dict})
    
    def _on_profile_changed(self, old_profile, new_profile) -> None:
        old_name = None
        new_name = None
        try:
            if old_profile:
                old_name = old_profile.name() if callable(getattr(old_profile, 'name', None)) else str(old_profile)
            if new_profile:
                new_name = new_profile.name() if callable(getattr(new_profile, 'name', None)) else str(new_profile)
        except:
            pass
        self._emit_event(EventType.PROFILE_CHANGED, {"old_profile": old_name, "new_profile": new_name})


# =============================================================================
# SECTION 8: BRIDGE GUI WINDOW
# =============================================================================

class BridgeWindow(QDialog):
    """Control window."""
    
    MAX_LOG_LINES = 500
    
    def __init__(self, bridge_plugin: 'MO2AIBridgePlugin', parent=None):
        super().__init__(parent)
        self._plugin = bridge_plugin
        self._log_lines = 0
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        self.setWindowTitle("MO2 AI Bridge v1.4")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        self._status_label = QLabel("Status: ---")
        self._status_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self._status_label)
        header.addStretch()
        self._port_label = QLabel("Port: ---")
        header.addWidget(self._port_label)
        layout.addLayout(header)
        
        tabs = QTabWidget()
        
        # Clients
        clients_widget = QWidget()
        clients_layout = QVBoxLayout(clients_widget)
        self._clients_list = QListWidget()
        clients_layout.addWidget(QLabel("Clients:"))
        clients_layout.addWidget(self._clients_list)
        self._external_list = QListWidget()
        clients_layout.addWidget(QLabel("Plugins:"))
        clients_layout.addWidget(self._external_list)
        tabs.addTab(clients_widget, "Connections")
        
        # Log
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        log_layout.addWidget(self._log_text)
        tabs.addTab(log_widget, "Log")
        
        # Methods (with batch highlighted)
        methods_widget = QWidget()
        methods_layout = QVBoxLayout(methods_widget)
        self._methods_list = QListWidget()
        methods_layout.addWidget(QLabel("API Methods (batch.* = optimized):"))
        methods_layout.addWidget(self._methods_list)
        tabs.addTab(methods_widget, "API")
        
        layout.addWidget(tabs)
        
        buttons = QHBoxLayout()
        
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self._on_restart)
        buttons.addWidget(restart_btn)
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear_log)
        buttons.addWidget(clear_btn)
        
        buttons.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        buttons.addWidget(close_btn)
        
        layout.addLayout(buttons)
    
    def _connect_signals(self) -> None:
        if self._plugin._server:
            self._plugin._server.client_connected.connect(lambda *a: self._update_clients())
            self._plugin._server.client_disconnected.connect(lambda *a: self._update_clients())
            self._plugin._server.error_occurred.connect(lambda e: self._log(f"Error: {e}"))
            self._plugin._server.server_started.connect(self._on_started)
            self._plugin._server.server_stopped.connect(self._on_stopped)
        
        if self._plugin._external_manager:
            self._plugin._external_manager.plugin_started.connect(lambda *a: self._update_externals())
            self._plugin._external_manager.plugin_crashed.connect(lambda n, e: self._log(f"Plugin {n} crashed"))
    
    def refresh_data(self) -> None:
        if self._plugin._api_executor:
            self._methods_list.clear()
            methods = sorted(self._plugin._api_executor.get_all_methods().keys())
            for name in methods:
                item = name
                if name.startswith("batch."):
                    item = f"⚡ {name}"  # Highlight batch methods
                self._methods_list.addItem(item)
        
        self._update_clients()
        self._update_externals()
        
        if self._plugin._server and self._plugin._server.is_running:
            self._on_started(self._plugin._server.port)
        else:
            self._on_stopped()
    
    def _update_clients(self) -> None:
        self._clients_list.clear()
        if self._plugin._server:
            for cid, client in self._plugin._server.connected_clients.items():
                self._clients_list.addItem(f"{client.name} ({client.address[0]})")
    
    def _update_externals(self) -> None:
        self._external_list.clear()
        if self._plugin._external_manager:
            for name, pid in self._plugin._external_manager.running_plugins.items():
                self._external_list.addItem(f"{name} (PID: {pid})")
    
    def _log(self, msg: str) -> None:
        if self._log_lines >= self.MAX_LOG_LINES:
            self._log_text.clear()
            self._log_lines = 0
        
        self._log_text.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        self._log_lines += 1
    
    def _clear_log(self) -> None:
        self._log_text.clear()
        self._log_lines = 0
    
    def _on_started(self, port: int) -> None:
        self._status_label.setText("Status: Running")
        self._status_label.setStyleSheet("font-weight: bold; color: green;")
        self._port_label.setText(f"Port: {port}")
    
    def _on_stopped(self) -> None:
        self._status_label.setText("Status: Stopped")
        self._status_label.setStyleSheet("font-weight: bold; color: red;")
    
    def log_event(self, event: BridgeMessage) -> None:
        self._log(f"Event: {event.event_type}")
    
    def _on_restart(self) -> None:
        self._plugin.restart_bridge()
        self._connect_signals()
        self.refresh_data()


# =============================================================================
# SECTION 9: MAIN PLUGIN CLASS
# =============================================================================

class MO2AIBridgePlugin(mobase.IPluginTool):
    """MO2 AI Bridge Plugin with Batch API support."""
    
    VERSION = "1.4.0"
    
    def __init__(self):
        super().__init__()
        self._organizer: Optional[mobase.IOrganizer] = None
        self._plugin_folder: Optional[Path] = None
        self._api_executor: Optional[APIExecutor] = None
        self._server: Optional[IPCServer] = None
        self._event_handler: Optional[MO2EventHandler] = None
        self._external_manager: Optional[ExternalPluginManager] = None
        self._window: Optional[BridgeWindow] = None
        self._initialized = False
    
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        self._plugin_folder = Path(__file__).parent
        
        print(f"[Bridge] Initializing v{self.VERSION} with Batch API...")
        
        try:
            self._api_executor = APIExecutor(organizer)
            
            self._event_handler = MO2EventHandler(organizer)
            self._event_handler.event_triggered.connect(self._on_event)
            
            self._server = IPCServer(self._api_executor)
            self._server.start()
            
            for _ in range(30):
                if self._server.is_running:
                    break
                time.sleep(0.1)
            
            if not self._server.is_running:
                print("[Bridge] Server failed to start")
                return False
            
            ext_folder = self._plugin_folder / "external_plugins"
            self._external_manager = ExternalPluginManager(ext_folder, self._server.port)
            
            QTimer.singleShot(3000, self._start_external_plugins)
            
            self._initialized = True
            
            # Log available batch methods
            batch_methods = [m for m in self._api_executor.get_all_methods().keys() if m.startswith("batch.")]
            print(f"[Bridge] Ready on port {self._server.port}")
            print(f"[Bridge] Batch methods available: {', '.join(batch_methods)}")
            
            return True
            
        except Exception as e:
            print(f"[Bridge] Init error: {e}")
            traceback.print_exc()
            return False
    
    def _start_external_plugins(self) -> None:
        if self._external_manager and self._server and self._server.is_running:
            self._external_manager.start_all_plugins()
            
            event = BridgeMessage.create_event(
                EventType.BRIDGE_STARTED,
                {"port": self._server.port, "version": self.VERSION}
            )
            self._server.broadcast_event(event)
    
    def _on_event(self, event: BridgeMessage) -> None:
        if self._server and self._server.is_running:
            self._server.broadcast_event(event)
        
        if self._window and self._window.isVisible():
            self._window.log_event(event)
    
    def name(self) -> str:
        return "MO2 AI Bridge"
    
    def author(self) -> str:
        return "AI Bridge Team"
    
    def description(self) -> str:
        return "API bridge with batch operations for external applications"
    
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 4, 0, mobase.ReleaseType.FINAL)
    
    def isActive(self) -> bool:
        return self._initialized
    
    def settings(self) -> List[mobase.PluginSetting]:
        return []
    
    def displayName(self) -> str:
        return "AI Bridge"
    
    def tooltip(self) -> str:
        return "Open AI Bridge control panel"
    
    def icon(self) -> QIcon:
        return QIcon()
    
    def display(self) -> None:
        if self._window is None:
            self._window = BridgeWindow(self)
        
        self._window.refresh_data()
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
    
    def restart_bridge(self) -> None:
        print("[Bridge] Restarting...")
        
        if self._server:
            self._server.stop()
        
        if self._api_executor:
            self._api_executor.cleanup()
        
        self._api_executor = APIExecutor(self._organizer)
        self._server = IPCServer(self._api_executor)
        self._server.start()
        
        for _ in range(30):
            if self._server.is_running:
                break
            time.sleep(0.1)
        
        if self._external_manager and self._server.is_running:
            self._external_manager.server_port = self._server.port
        
        print(f"[Bridge] Restarted on port {self._server.port}")
    
    def __del__(self):
        try:
            if self._external_manager:
                self._external_manager.stop_all_plugins()
            if self._server:
                self._server.stop()
            if self._api_executor:
                self._api_executor.cleanup()
            _event_pool.clear()
        except Exception:
            pass


def createPlugin() -> mobase.IPlugin:
    return MO2AIBridgePlugin()