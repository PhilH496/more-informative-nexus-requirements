#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MO2 API Bridge Client Library
==============================
Client library for connecting to the MO2 AI Bridge.
===================================================
Original code by AlhimikPh on nexusmods.com
"""

import os
import json
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HANDSHAKE = "handshake"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class BridgeMessage:
    """Message structure for bridge communication."""
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


class MO2BridgeClient:
    """Client for connecting to the MO2 AI Bridge."""
    
    MESSAGE_DELIMITER = b'\n\x00\x00\n'
    
    def __init__(self, host: str = None, port: int = None, name: str = None):
        self.host = host or os.environ.get('MO2_BRIDGE_HOST', '127.0.0.1')
        self.port = port or int(os.environ.get('MO2_BRIDGE_PORT', '52525'))
        self.name = name or os.environ.get('MO2_PLUGIN_NAME', 'TestClient')
        
        self._socket: Optional[socket.socket] = None
        self._client_id: Optional[str] = None
        self._connected = False
        self._running = False
        
        self._recv_thread: Optional[threading.Thread] = None
        self._pending_requests: Dict[str, threading.Event] = {}
        self._responses: Dict[str, BridgeMessage] = {}
        self._responses_lock = threading.Lock()
        
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._available_methods: List[str] = []
    
    def connect(self) -> bool:
        """Connect to the MO2 bridge server."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(10)
            self._socket.connect((self.host, self.port))
            self._connected = True
            self._running = True
            
            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()
            
            time.sleep(0.5)
            
            handshake = BridgeMessage(
                type=MessageType.HANDSHAKE.value,
                kwargs={"name": self.name, "subscribe_events": ["*"]}
            )
            self._send(handshake)
            
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the bridge server."""
        self._running = False
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
    
    def _send(self, message: BridgeMessage) -> bool:
        try:
            data = message.to_json().encode('utf-8') + self.MESSAGE_DELIMITER
            self._socket.sendall(data)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def _receive_loop(self) -> None:
        buffer = b""
        while self._running:
            try:
                self._socket.settimeout(1.0)
                data = self._socket.recv(65536)
                if not data:
                    break
                buffer += data
                while self.MESSAGE_DELIMITER in buffer:
                    msg_data, buffer = buffer.split(self.MESSAGE_DELIMITER, 1)
                    self._process_message(msg_data.decode('utf-8'))
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"Receive error: {e}")
                break
        self._connected = False
    
    def _process_message(self, msg_json: str) -> None:
        try:
            message = BridgeMessage.from_json(msg_json)
            if message.type == MessageType.HANDSHAKE.value:
                if message.result:
                    self._client_id = message.result.get('client_id')
                    self._available_methods = message.result.get('available_methods', [])
                    print(f"Connected! Client ID: {self._client_id}")
                    print(f"Available methods: {len(self._available_methods)}")
            elif message.type == MessageType.RESPONSE.value:
                with self._responses_lock:
                    self._responses[message.id] = message
                event = self._pending_requests.get(message.id)
                if event:
                    event.set()
            elif message.type == MessageType.EVENT.value:
                self._handle_event(message)
        except Exception as e:
            print(f"Message processing error: {e}")
    
    def _handle_event(self, message: BridgeMessage) -> None:
        event_type = message.event_type
        event_data = message.event_data
        handlers = self._event_handlers.get(event_type, [])
        handlers += self._event_handlers.get('*', [])
        for handler in handlers:
            try:
                handler(event_type, event_data)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    def call(self, method: str, *args, timeout: float = 30.0, **kwargs) -> Any:
        """Call an MO2 API method."""
        request = BridgeMessage(
            type=MessageType.REQUEST.value,
            method=method,
            args=list(args),
            kwargs=kwargs
        )
        
        event = threading.Event()
        self._pending_requests[request.id] = event
        
        if not self._send(request):
            del self._pending_requests[request.id]
            raise Exception("Failed to send request")
        
        if not event.wait(timeout=timeout):
            del self._pending_requests[request.id]
            raise Exception("Request timeout")
        
        with self._responses_lock:
            response = self._responses.pop(request.id, None)
        del self._pending_requests[request.id]
        
        if response is None:
            raise Exception("No response received")
        
        if response.error:
            raise Exception(f"{response.error}")
        
        return response.result
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    @property
    def is_connected(self) -> bool:
        return self._connected
