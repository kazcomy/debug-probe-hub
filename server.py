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
import cgi
import io
import fcntl
import time
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
        elif parsed_path == '/session/stop':
            self._handle_session_stop()
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
                compatible_probes = target_config.get("compatible_probes", [])
                transports = {}
                for interface in compatible_probes:
                    transports[interface] = {
                        "default": config.get_default_transport(name, interface),
                        "allowed": config.get_allowed_transports(name, interface),
                    }
                targets[name] = {
                    "description": target_config.get("description", ""),
                    "compatible_probes": compatible_probes,
                    "compatible_interfaces": compatible_probes,
                    "container": target_config.get("container", ""),
                    "transports": transports,
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
            transport = form_data.get("transport")

            if not all([target, probe_id, mode]):
                raise ValueError("Missing required fields: target, probe, mode")

            if mode not in ["debug", "flash", "print"]:
                raise ValueError(f"Invalid mode: {mode}. Must be 'debug', 'flash', or 'print'")

            probe_id = int(probe_id)

            # Validate configuration
            if not config.get_target(target):
                raise ValueError(f"Unknown target: {target}")

            probe = config.get_probe(probe_id)
            if not probe:
                raise ValueError(f"Unknown probe ID: {probe_id}")

            if not config.is_probe_compatible(target, probe_id):
                raise ValueError(f"Probe {probe_id} is not compatible with target {target}")

            interface = probe.get("interface", "")
            try:
                resolved_transport = config.resolve_transport(
                    target_name=target,
                    interface=interface,
                    requested_transport=transport,
                    mode=mode,
                )
                config.validate_probe_transport(
                    target_name=target,
                    interface=interface,
                    probe=probe,
                    requested_transport=transport,
                    resolved_transport=resolved_transport,
                    mode=mode,
                )
            except ValueError as e:
                raise ValueError(str(e))

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
                filename if firmware_path else "",
                resolved_transport or "",
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

    def _list_probe_containers(self, probe_id: int):
        """List candidate container names for a probe suffix and config-defined services."""
        names = set()
        suffix = f"-p{probe_id}"

        # Prefer real container names from Docker.
        docker_ps = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        if docker_ps.returncode == 0:
            for line in docker_ps.stdout.splitlines():
                name = line.strip()
                if name.endswith(suffix):
                    names.add(name)

        # Add config-derived names as fallback.
        for container in config.get_all_containers().values():
            base = container.get("name")
            if base:
                names.add(f"{base}{suffix}")

        return sorted(names)

    def _is_container_running(self, container_name: str) -> bool:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def _pkill_pattern(self, container_name: str, pattern: str) -> None:
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "-f", "--", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_probe_processes(self, container_name: str, probe_id: int, kind: str) -> None:
        gdb_port = config.gdb_base_port + probe_id
        rtt_port = config.rtt_base_port + probe_id

        if kind in ("debug", "all"):
            for pattern in [
                f"gdb_port {gdb_port}",
                f"-port {gdb_port}",
                f":{gdb_port}",
                "JLinkGDBServer",
                "openocd",
            ]:
                self._pkill_pattern(container_name, pattern)

        if kind in ("print", "all"):
            for pattern in [
                f"RTTTelnetPort {rtt_port}",
                f"TCP-LISTEN:{rtt_port}",
                f":{rtt_port}",
                f"Starting print server (probe {probe_id})",
                "JLinkRTTClient",
                "wlink",
                "socat",
            ]:
                self._pkill_pattern(container_name, pattern)

    def _wait_lock_release(self, probe_id: int, timeout_seconds: float = 5.0, poll_seconds: float = 0.2) -> bool:
        lock_path = Path(f"/var/lock/probe_{probe_id}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + timeout_seconds

        with open(lock_path, "w") as lock_file:
            while time.time() < deadline:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                    return True
                except BlockingIOError:
                    time.sleep(poll_seconds)

        return False

    def _handle_session_stop(self):
        """Stop active debug/print session for a probe and wait lock release."""
        logs = []
        try:
            content_type = self.headers.get("Content-Type")
            if not content_type:
                raise ValueError("Content-Type header missing")

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            form_data, _, _ = self._parse_multipart(content_type, body)

            probe_raw = form_data.get("probe")
            if not probe_raw:
                raise ValueError("Missing required field: probe")

            kind = (form_data.get("kind") or "all").strip().lower()
            if kind not in {"debug", "print", "all"}:
                raise ValueError("Invalid kind. Must be one of: debug, print, all")

            probe_id = int(probe_raw)
            probe = config.get_probe(probe_id)
            if not probe:
                raise ValueError(f"Unknown probe ID: {probe_id}")

            logs.append(f"Target probe: {probe['name']} (ID: {probe_id})")
            logs.append(f"Requested kind: {kind}")

            container_names = self._list_probe_containers(probe_id)
            if not container_names:
                logs.append("No candidate containers found for this probe.")
            else:
                logs.append("Candidate containers: " + ", ".join(container_names))

            for container_name in container_names:
                if not self._is_container_running(container_name):
                    logs.append(f"[SKIP] {container_name}: not running")
                    continue

                logs.append(f"[STOP] {container_name}: sending pkill patterns")
                self._stop_probe_processes(container_name, probe_id, kind)

            released = self._wait_lock_release(probe_id)
            if released:
                logs.append("Lock release confirmed (flock acquirable)")
                self._send_json(200, {"status": "ok", "log": "\n".join(logs)})
            else:
                logs.append("Lock still held after timeout (5s)")
                self._send_json(500, {"status": "error", "log": "\n".join(logs)})

        except Exception as e:
            print(f"[ERROR] Session stop failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            logs.append(f"Error: {e}")
            self._send_json(500, {"status": "error", "log": "\n".join(logs), "error": str(e)})

    def _parse_multipart(self, content_type, body):
        """Parse multipart form data"""
        # Create file-like object from body
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': len(body)
        }

        form = cgi.FieldStorage(
            fp=io.BytesIO(body),
            environ=environ,
            keep_blank_values=True
        )

        form_data = {}
        file_data = None
        filename = "firmware.bin"

        # Extract form fields
        for key in form.keys():
            item = form[key]
            item_filename = getattr(item, "filename", None)
            if item_filename:  # File upload
                filename = os.path.basename(item_filename)
                file_data = item.file.read()
            else:  # Regular form field
                form_data[key] = item.value

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
