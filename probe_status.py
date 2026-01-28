#!/usr/bin/env python3
"""
Probe Status Reporter
Reports connection status of all configured probes
"""
import json
import subprocess
import sys
from pathlib import Path
from config_loader import get_config

def get_device_info(probe_id):
    """Get device information from udev"""
    dev_path = f"/dev/probes/probe_{probe_id}"

    if not Path(dev_path).exists():
        return None

    try:
        # Query udev for device properties
        result = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name={dev_path}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        properties = {}
        for line in result.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                properties[key] = value

        # Extract serial number
        serial = properties.get('ID_SERIAL_SHORT', properties.get('ID_SERIAL', ''))

        return {
            'connected': True,
            'serial': serial,
            'vendor_id': properties.get('ID_VENDOR_ID', ''),
            'product_id': properties.get('ID_MODEL_ID', '')
        }

    except Exception as e:
        print(f"Error querying device {dev_path}: {e}", file=sys.stderr)
        return None

def main():
    config = get_config()
    probes = config.get_all_probes()

    status_list = []

    for probe in probes:
        probe_id = probe['id']
        name = probe['name']
        expected_serial = probe.get('serial', '')

        device_info = get_device_info(probe_id)

        if device_info:
            status = {
                'id': probe_id,
                'name': name,
                'status': 'connected',
                'serial': device_info['serial'],
                'expected_serial': expected_serial,
                'match': device_info['serial'] == expected_serial if expected_serial else True
            }
        else:
            status = {
                'id': probe_id,
                'name': name,
                'status': 'disconnected',
                'serial': '',
                'expected_serial': expected_serial,
                'match': False
            }

        status_list.append(status)

    # Output JSON
    print(json.dumps(status_list, indent=2))

if __name__ == '__main__':
    main()
