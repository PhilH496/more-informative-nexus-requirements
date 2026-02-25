#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
More Informative Nexus Requirements Server
==========================================
API for fetching mo2 mod info.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from .bridge_client import MO2BridgeClient
from .more_informative_nexus_requirements import getEnabledModIds, getModIds

PORT = 52526
class MoreInformativeNexusRequirementsAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # suppress logs
        pass

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

def run(server_class=ThreadingHTTPServer, handler_class=MoreInformativeNexusRequirementsAPIHandler, client=None):
    """
    Run the server.
    """
    if client is None:
        client = MO2BridgeClient(name="MoreInformativeNexusRequirements")
        print("\nConnecting to MO2 Bridge...")
        if not client.connect():
            print("Failed to connect. Make sure MO2 is running and the AI Bridge plugin is installed.")
            return
        own_client = True
    else:
        own_client = False

    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    httpd.mo2_client = client

    if own_client:
        print(f"Server running on port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        if own_client:
            print("\nShutting down...")
            client.disconnect()
        httpd.server_close()


if __name__ == '__main__':
    run()