#!/usr/bin/env python3
"""
Debugger Station HTTP Server
Provides REST API for firmware flashing and debugging
"""
import http.server
import socketserver
import subprocess
import json
import os
import sys
import email.message
from urllib.parse import urlparse
from pathlib import Path
from config_loader import get_config
from probe_finder import search_probes

config = get_config()

PORT = config.server_port
UPLOAD_DIR = config.upload_dir

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to log to stderr for journalctl compatibility"""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        parsed_path = urlparse(self.path).path.rstrip("/")
        print(f"[DEBUG] GET {parsed_path}", file=sys.stderr)

        if parsed_path == '/status':
            self._handle_status()
        elif parsed_path == '/probes':
            self._handle_probes_list()
        elif parsed_path.startswith('/probes/search'):
            self._handle_probe_search()
        elif parsed_path == '/targets':
            self._handle_targets_list()
        else:
            self._send_error(404, "Not Found", {"path": self.path})

    def do_POST(self):
        parsed_path = urlparse(self.path).path.rstrip("/")
        print(f"[DEBUG] POST {parsed_path}", file=sys.stderr)

        if parsed_path == '/dispatch':
            self._handle_dispatch()
        else:
            self._send_error(404, "Not Found")

    def _handle_status(self):
        """Get status of all probes"""
        try:
            script_path = Path(__file__).parent / "probe_status.py"
            out = subprocess.check_output([sys.executable, str(script_path)])
            self._send_json(200, json.loads(out))
        except Exception as e:
            print(f"[ERROR] probe_status failed: {e}", file=sys.stderr)
            self._send_json(500, {"error": str(e)})

    def _handle_probes_list(self):
        """List all configured probes"""
        try:
            probes = config.get_all_probes()
            self._send_json(200, {"probes": probes})
        except Exception as e:
            print(f"[ERROR] Failed to list probes: {e}", file=sys.stderr)
            self._send_json(500, {"error": str(e)})

    def _handle_targets_list(self):
        """List all supported targets"""
        try:
            targets = {}
            for name, target_config in config.get_all_targets().items():
                targets[name] = {
                    "description": target_config.get("description", ""),
                    "compatible_probes": target_config.get("compatible_probes", []),
                    "container": target_config.get("container", "")
                }
            self._send_json(200, {"targets": targets})
        except Exception as e:
            print(f"[ERROR] Failed to list targets: {e}", file=sys.stderr)
            self._send_json(500, {"error": str(e)})

    def _handle_probe_search(self):
        """Search for probes by various criteria"""
        try:
            from urllib.parse import parse_qs

            # Parse query parameters
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)

            # Extract search criteria (take first value from lists)
            interface = query_params.get('interface', [None])[0]
            vendor_id = query_params.get('vid', query_params.get('vendor_id', [None]))[0]
            product_id = query_params.get('pid', query_params.get('product_id', [None]))[0]
            serial = query_params.get('serial', [None])[0]
            name = query_params.get('name', [None])[0]

            # Perform search
            results = search_probes(
                interface=interface,
                vendor_id=vendor_id,
                product_id=product_id,
                serial=serial,
                name=name
            )

            self._send_json(200, results)

        except Exception as e:
            print(f"[ERROR] Probe search failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            self._send_json(500, {"error": str(e)})

    def _handle_dispatch(self):
        """Handle firmware dispatch request"""
        try:
            content_type = self.headers.get('Content-Type')
            if not content_type:
                raise ValueError("Content-Type header missing")

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # Parse multipart form data
            form_data, file_data, filename = self._parse_multipart(content_type, body)

            target = form_data.get("target")
            probe_id = form_data.get("probe")
            mode = form_data.get("mode")

            if not all([target, probe_id, mode]):
                raise ValueError("Missing required fields: target, probe, mode")

            probe_id = int(probe_id)

            # Validate configuration
            if not config.get_target(target):
                raise ValueError(f"Unknown target: {target}")

            if not config.get_probe(probe_id):
                raise ValueError(f"Unknown probe ID: {probe_id}")

            if not config.is_probe_compatible(target, probe_id):
                raise ValueError(f"Probe {probe_id} is not compatible with target {target}")

            # Save firmware file if provided
            firmware_path = None
            if file_data and mode == "flash":
                firmware_path = os.path.join(UPLOAD_DIR, filename)
                with open(firmware_path, 'wb') as f:
                    f.write(file_data)
                print(f"[DEBUG] Saved firmware: {firmware_path}", file=sys.stderr)

            # Execute dispatcher
            script_path = Path(__file__).parent / "debug_dispatcher.py"
            cmd = [
                sys.executable,
                str(script_path),
                target,
                str(probe_id),
                mode,
                filename if firmware_path else ""
            ]

            print(f"[DEBUG] Executing: {' '.join(cmd)}", file=sys.stderr)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            resp = {
                "status": "ok" if res.returncode == 0 else "error",
                "log": res.stdout + res.stderr
            }
            self._send_json(200 if res.returncode == 0 else 500, resp)

        except Exception as e:
            print(f"[ERROR] Dispatch failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            self._send_json(500, {"status": "error", "error": str(e)})

    def _parse_multipart(self, content_type, body):
        """Parse multipart form data"""
        msg = email.message.Message()
        msg['Content-Type'] = content_type
        msg.set_payload(body)

        form_data = {}
        file_data = None
        filename = "firmware.bin"

        if msg.is_multipart():
            for part in msg.get_payload():
                name = part.get_param('name', header='content-disposition')
                if name == 'file':
                    fn = part.get_param('filename', header='content-disposition')
                    if fn:
                        filename = os.path.basename(fn)
                    file_data = part.get_payload(decode=True)
                elif name:
                    payload = part.get_payload(decode=True)
                    if payload:
                        form_data[name] = payload.decode('utf-8').strip()

        return form_data, file_data, filename

    def _send_json(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, status_code, message, extra=None):
        """Send error response"""
        error_data = {"error": message}
        if extra:
            error_data.update(extra)
        self._send_json(status_code, error_data)

def main():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Debugger Station server listening on 0.0.0.0:{PORT}", file=sys.stderr)
        print(f"Upload directory: {UPLOAD_DIR}", file=sys.stderr)
        httpd.serve_forever()

if __name__ == '__main__':
    main()
