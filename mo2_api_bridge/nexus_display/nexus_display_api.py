#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus Display API
=================
API server for displaying Nexus mod information.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
from bridge_client import MO2BridgeClient
from nexus_display import getEnabledModIds, getModIds

PORT = 52526
class NexusDisplayAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.client = MO2BridgeClient(name="NexusDisplay")
        print("\nConnecting to MO2 Bridge...")
        if not self.client.connect():
            print("Failed to connect. Make sure MO2 is running and the AI Bridge plugin is installed.")
            exit(1)
        super().__init__(*args, **kwargs)
    
    def ok_response(self):
        """Send a 200 OK response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        """Handles GET requests."""
        if self.path == '/api/status':
            self.ok_response()
            self.wfile.write(b'{"status": "ok"}')
        elif self.path == '/api/mod-ids':
            self.ok_response()
            mod_ids = getModIds(self.client)
            self.wfile.write(json.dumps(mod_ids).encode('utf-8'))
        elif self.path == '/api/mod-ids/enabled':
            self.ok_response()
            enabled_ids = getEnabledModIds(self.client)
            self.wfile.write(json.dumps(enabled_ids).encode('utf-8'))
            
# TODO: Implement API endpoints
# GET  /api/mod-ids/tracked       - Returns all tracked Nexus mod IDs
# GET  /api/mod-ids/endorsements  - Returns all endorsed Nexus mod IDs
def run(server_class=HTTPServer, handler_class=NexusDisplayAPIHandler):
    """Runs the API server."""
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == '__main__':
    run()