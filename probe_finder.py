#!/usr/bin/env python3
"""
Probe Finder
Find probes by interface name, VID/PID, or serial number
"""
import json
import sys
from typing import List, Dict, Optional
from config_loader import get_config

def normalize_interface_name(name: str) -> str:
    """Normalize interface name for matching"""
    name = name.lower().replace('-', '').replace('_', '')

    # Common aliases
    aliases = {
        'jlink': ['jlink', 'segger', 'swd'],
        'cmsisdap': ['cmsisdap', 'cmsis', 'dap'],
        'wchlink': ['wchlink', 'wch', 'wchlinke'],
    }

    for key, values in aliases.items():
        if name in values:
            return key

    return name

def find_probes_by_interface(interface_name: str) -> List[Dict]:
    """
    Find all probes matching an interface type

    Args:
        interface_name: Interface name (e.g., "JLink", "CMSIS-DAP", "WCH-Link")

    Returns:
        List of matching probes
    """
    config = get_config()
    probes = config.get_all_probes()

    normalized_query = normalize_interface_name(interface_name)
    matches = []

    for probe in probes:
        probe_interface = normalize_interface_name(probe.get('interface', ''))

        if probe_interface == normalized_query:
            matches.append(probe)

    return matches

def find_probe_by_vid_pid(vendor_id: str, product_id: str, serial: Optional[str] = None) -> List[Dict]:
    """
    Find probes by VID/PID and optionally serial number

    Args:
        vendor_id: Vendor ID (e.g., "1366")
        product_id: Product ID (e.g., "0105")
        serial: Optional serial number for disambiguation

    Returns:
        List of matching probes
    """
    config = get_config()
    probes = config.get_all_probes()

    # Normalize IDs (remove common prefixes)
    vendor_id = vendor_id.lower().replace('0x', '')
    product_id = product_id.lower().replace('0x', '')

    matches = []

    for probe in probes:
        probe_vid = probe.get('vendor_id', '').lower().replace('0x', '')
        probe_pid = probe.get('product_id', '').lower().replace('0x', '')

        if probe_vid == vendor_id and probe_pid == product_id:
            # If serial is specified, check it
            if serial is None or probe.get('serial', '') == serial:
                matches.append(probe)

    return matches

def find_probe_by_serial(serial: str) -> Optional[Dict]:
    """
    Find a specific probe by serial number

    Args:
        serial: Serial number

    Returns:
        Matching probe or None
    """
    config = get_config()
    probes = config.get_all_probes()

    for probe in probes:
        if probe.get('serial', '') == serial:
            return probe

    return None

def find_probe_by_name(name: str) -> List[Dict]:
    """
    Find probes by partial name match

    Args:
        name: Part of the probe name

    Returns:
        List of matching probes
    """
    config = get_config()
    probes = config.get_all_probes()

    name_lower = name.lower()
    matches = []

    for probe in probes:
        probe_name = probe.get('name', '').lower()
        if name_lower in probe_name:
            matches.append(probe)

    return matches

def search_probes(
    interface: Optional[str] = None,
    vendor_id: Optional[str] = None,
    product_id: Optional[str] = None,
    serial: Optional[str] = None,
    name: Optional[str] = None
) -> Dict:
    """
    Search for probes with various criteria

    Args:
        interface: Interface type (e.g., "jlink", "cmsis-dap")
        vendor_id: USB Vendor ID
        product_id: USB Product ID
        serial: Serial number
        name: Probe name (partial match)

    Returns:
        Search results with matches
    """
    config = get_config()
    all_probes = config.get_all_probes()
    matches = []

    # If no criteria specified, return all probes
    if not any([interface, vendor_id, product_id, serial, name]):
        return {
            "query": {},
            "matches": all_probes,
            "count": len(all_probes)
        }

    # Start with all probes and filter down
    candidates = all_probes.copy()

    # Filter by interface
    if interface:
        normalized_interface = normalize_interface_name(interface)
        candidates = [
            p for p in candidates
            if normalize_interface_name(p.get('interface', '')) == normalized_interface
        ]

    # Filter by VID
    if vendor_id:
        vid_normalized = vendor_id.lower().replace('0x', '')
        candidates = [
            p for p in candidates
            if p.get('vendor_id', '').lower().replace('0x', '') == vid_normalized
        ]

    # Filter by PID
    if product_id:
        pid_normalized = product_id.lower().replace('0x', '')
        candidates = [
            p for p in candidates
            if p.get('product_id', '').lower().replace('0x', '') == pid_normalized
        ]

    # Filter by serial
    if serial:
        candidates = [
            p for p in candidates
            if p.get('serial', '') == serial
        ]

    # Filter by name
    if name:
        name_lower = name.lower()
        candidates = [
            p for p in candidates
            if name_lower in p.get('name', '').lower()
        ]

    return {
        "query": {
            "interface": interface,
            "vendor_id": vendor_id,
            "product_id": product_id,
            "serial": serial,
            "name": name
        },
        "matches": candidates,
        "count": len(candidates)
    }

def main():
    """Command-line interface for probe search"""
    import argparse

    parser = argparse.ArgumentParser(description='Search for debug probes')
    parser.add_argument('-i', '--interface', help='Interface type (jlink, cmsis-dap, wch-link)')
    parser.add_argument('-v', '--vendor-id', help='USB Vendor ID')
    parser.add_argument('-p', '--product-id', help='USB Product ID')
    parser.add_argument('-s', '--serial', help='Serial number')
    parser.add_argument('-n', '--name', help='Probe name (partial match)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    # Perform search
    results = search_probes(
        interface=args.interface,
        vendor_id=args.vendor_id,
        product_id=args.product_id,
        serial=args.serial,
        name=args.name
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Human-readable output
        print(f"Search query: {results['query']}")
        print(f"Found {results['count']} probe(s):\n")

        for probe in results['matches']:
            print(f"ID: {probe['id']}")
            print(f"Name: {probe['name']}")
            print(f"Interface: {probe['interface']}")
            print(f"VID:PID: {probe['vendor_id']}:{probe['product_id']}")
            print(f"Serial: {probe.get('serial', 'N/A')}")
            print()

if __name__ == '__main__':
    main()
