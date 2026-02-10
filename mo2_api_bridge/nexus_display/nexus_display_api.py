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
from nexus_display import getModIds
class NexusDisplayAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.client = MO2BridgeClient(name="NexusDisplay")
        print("\nConnecting to MO2 Bridge...")
        if not self.client.connect():
            print("Failed to connect. Make sure MO2 is running and the AI Bridge plugin is installed.")
            exit(1)
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        elif self.path == '/api/mod-ids':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            mod_ids = getModIds(self.client)
            self.wfile.write(json.dumps(mod_ids).encode('utf-8'))
# TODO: Implement API endpoints
# GET  /api/mod-ids/downloaded    - Returns all downloaded Nexus mod IDs
# GET  /api/mod-ids/enabled       - Returns all enabled Nexus mod IDs
# GET  /api/mod-ids/tracked       - Returns all tracked Nexus mod IDs
# GET  /api/mod-ids/endorsements  - Returns all endorsed Nexus mod IDs
def run(server_class=HTTPServer, handler_class=NexusDisplayAPIHandler):
    server_address = ('', 52526)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == '__main__':
    run()