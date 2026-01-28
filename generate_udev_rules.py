#!/usr/bin/env python3
"""
Generate udev rules from config.yml
"""
import yaml
import sys
from pathlib import Path

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_udev_rules(config):
    rules = []
    rules.append("# Auto-generated udev rules for Debug Probe Hub")
    rules.append("# Generated from config.yml\n")

    for probe in config['probes']:
        probe_id = probe['id']
        name = probe['name']
        vendor_id = probe['vendor_id']
        product_id = probe['product_id']
        serial = probe.get('serial', '')

        # Create rule with serial number match
        if serial:
            rule = (
                f'# {name}\n'
                f'SUBSYSTEM=="usb", '
                f'ATTRS{{idVendor}}=="{vendor_id}", '
                f'ATTRS{{idProduct}}=="{product_id}", '
                f'ATTRS{{serial}}=="{serial}", '
                f'MODE="0666", '
                f'SYMLINK+="probes/probe_{probe_id}"\n'
            )
        else:
            # Rule without serial (less specific)
            rule = (
                f'# {name}\n'
                f'SUBSYSTEM=="usb", '
                f'ATTRS{{idVendor}}=="{vendor_id}", '
                f'ATTRS{{idProduct}}=="{product_id}", '
                f'MODE="0666", '
                f'SYMLINK+="probes/probe_{probe_id}"\n'
            )

        rules.append(rule)

    return '\n'.join(rules)

def main():
    config_path = Path(__file__).parent / 'config.yml'

    if not config_path.exists():
        print(f"Error: {config_path} not found", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    rules = generate_udev_rules(config)

    # Write to stdout or file
    output_path = Path(__file__).parent / '99-debug-probe-hub.rules'
    with open(output_path, 'w') as f:
        f.write(rules)

    print(f"Generated udev rules: {output_path}")
    print("\nTo install:")
    print(f"  sudo cp {output_path} /etc/udev/rules.d/")
    print("  sudo udevadm control --reload-rules")
    print("  sudo udevadm trigger")

if __name__ == '__main__':
    main()
