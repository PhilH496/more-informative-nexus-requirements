#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus Display API
=================
API server for displaying Nexus mod information.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from bridge_client import MO2BridgeClient
from nexus_display import getEnabledModIds, getModIds

PORT = 52526
class NexusDisplayAPIHandler(BaseHTTPRequestHandler):

    @property
    def client(self):
        return self.server.mo2_client

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
            try:
                mod_ids = getModIds(self.client)
                self.wfile.write(json.dumps(mod_ids).encode('utf-8'))
            except Exception as e:
                print(f"Error getting mod ids: {e}")
                self.wfile.write(b'{"nexus_ids": []}')
        elif self.path == '/api/mod-ids/enabled':
            self.ok_response()
            try:
                enabled_ids = getEnabledModIds(self.client)
                self.wfile.write(json.dumps(enabled_ids).encode('utf-8'))
            except Exception as e:
                print(f"Error getting enabled ids: {e}")
                self.wfile.write(b'{"enabled_ids": []}')
            
# TODO: Implement API endpoints
# GET  /api/mod-ids/tracked       - Returns all tracked Nexus mod IDs
# GET  /api/mod-ids/endorsements  - Returns all endorsed Nexus mod IDs
def run(server_class=ThreadingHTTPServer, handler_class=NexusDisplayAPIHandler):
    """Runs the API server."""
    client = MO2BridgeClient(name="NexusDisplay")
    print("\nConnecting to MO2 Bridge...")
    if not client.connect():
        print("Failed to connect. Make sure MO2 is running and the AI Bridge plugin is installed.")
    
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    # reuse client otherwise will have issues with opening multiple web pages with multiple connections
    httpd.mo2_client = client
    
    print(f"Server running on port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.disconnect()
        httpd.server_close()

if __name__ == '__main__':
    run()