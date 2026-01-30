#!/usr/bin/env python3
"""
Debug Dispatcher
Executes debug or flash commands based on configuration
"""
import sys
import subprocess
import fcntl
from pathlib import Path
from config_loader import get_config

def acquire_lock(probe_id):
    """Acquire exclusive lock for probe"""
    lock_path = f"/var/lock/probe_{probe_id}.lock"
    Path("/var/lock").mkdir(parents=True, exist_ok=True)

    lock_file = open(lock_path, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except BlockingIOError:
        print(f"Error: Probe #{probe_id} is busy", file=sys.stderr)
        sys.exit(1)

def get_gdb_port(probe_id):
    """Calculate GDB port for probe"""
    config = get_config()
    return config.gdb_base_port + probe_id

def get_telnet_port(probe_id):
    """Calculate Telnet port for probe"""
    config = get_config()
    return config.telnet_base_port + probe_id

def get_rtt_port(probe_id):
    """Calculate RTT/print port for probe"""
    config = get_config()
    return config.rtt_base_port + probe_id

def cleanup_existing_processes(container_name, probe_id, interface):
    """Kill existing debug server processes"""
    gdb_port = get_gdb_port(probe_id)
    rtt_port = get_rtt_port(probe_id)

    # Kill processes listening on GDB port
    subprocess.run(
        ["docker", "exec", container_name, "pkill", "-f", f"gdb_port {gdb_port}"],
        stderr=subprocess.DEVNULL
    )

    # Kill processes listening on RTT/print port
    subprocess.run(
        ["docker", "exec", container_name, "pkill", "-f", f"RTTTelnetPort {rtt_port}"],
        stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["docker", "exec", container_name, "pkill", "-f", f"TCP-LISTEN:{rtt_port}"],
        stderr=subprocess.DEVNULL
    )

    # Kill interface-specific processes
    if interface == "jlink":
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "JLinkGDBServer"],
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "JLinkRTTClient"],
            stderr=subprocess.DEVNULL
        )
    elif interface == "wch-link":
        # Kill OpenOCD and wlink processes
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "openocd"],
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "wlink"],
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "socat"],
            stderr=subprocess.DEVNULL
        )

def execute_command(container_name, command, mode, probe_id=None):
    """Execute command in Docker container"""
    if mode == "print":
        # Print mode with auto-restart on disconnect
        restart_cmd = f"""
while true; do
    echo "[$(date)] Starting print server (probe {probe_id})..." | tee -a /tmp/print.log
    {command} 2>&1 | tee -a /tmp/print.log
    echo "[$(date)] Print server disconnected, restarting in 2s..." | tee -a /tmp/print.log
    sleep 2
done
"""
        result = subprocess.run(
            ["docker", "exec", "-d", container_name, "/bin/bash", "-c", restart_cmd],
            capture_output=True,
            text=True
        )
        print(f"Print server started with auto-restart: {command}")
        return result
    elif mode == "debug":
        # Start debug server in background
        full_cmd = f"nohup {command} > /tmp/debug.log 2>&1 &"
        result = subprocess.run(
            ["docker", "exec", "-d", container_name, "/bin/bash", "-c", full_cmd],
            capture_output=True,
            text=True
        )
        print(f"Debug server started: {command}")
        return result
    else:
        # Flash mode - run synchronously
        result = subprocess.run(
            ["docker", "exec", container_name, "/bin/bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=120
        )
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result

def main():
    if len(sys.argv) < 4:
        print("Usage: debug_dispatcher.py <target> <probe_id> <mode> [firmware_file]", file=sys.stderr)
        sys.exit(1)

    target_name = sys.argv[1]
    probe_id = int(sys.argv[2])
    mode = sys.argv[3]
    firmware_file = sys.argv[4] if len(sys.argv) > 4 else ""

    if mode not in ["debug", "flash", "print"]:
        print(f"Error: Invalid mode '{mode}'. Must be 'debug', 'flash', or 'print'", file=sys.stderr)
        sys.exit(1)

    config = get_config()

    # Validate target
    target = config.get_target(target_name)
    if not target:
        print(f"Error: Unknown target '{target_name}'", file=sys.stderr)
        sys.exit(1)

    # Validate probe
    probe = config.get_probe(probe_id)
    if not probe:
        print(f"Error: Unknown probe ID {probe_id}", file=sys.stderr)
        sys.exit(1)

    # Check compatibility
    if not config.is_probe_compatible(target_name, probe_id):
        print(f"Error: Probe {probe_id} is not compatible with target {target_name}", file=sys.stderr)
        sys.exit(1)

    # Get container
    container_name = config.get_container_for_target(target_name)
    if not container_name:
        print(f"Error: No container configured for target {target_name}", file=sys.stderr)
        sys.exit(1)

    # Acquire lock
    lock_file = acquire_lock(probe_id)

    try:
        # Get command template
        interface = probe['interface']
        command_template = config.get_command(target_name, interface, mode)

        if not command_template:
            print(f"Error: No command defined for target={target_name}, interface={interface}, mode={mode}", file=sys.stderr)
            sys.exit(1)

        # Format command with parameters
        firmware_path = f"/work/{firmware_file}" if firmware_file else ""
        device_path = config.get_probe_device_path(probe_id) or ""

        command = config.format_command(
            command_template,
            serial=probe['serial'],
            gdb_port=get_gdb_port(probe_id),
            telnet_port=get_telnet_port(probe_id),
            rtt_port=get_rtt_port(probe_id),
            print_port=get_rtt_port(probe_id),
            device_path=device_path,
            firmware_path=firmware_path
        )

        print(f"Target: {target_name}", file=sys.stderr)
        print(f"Probe: {probe['name']} (ID: {probe_id})", file=sys.stderr)
        print(f"Mode: {mode}", file=sys.stderr)
        print(f"Container: {container_name}", file=sys.stderr)
        print(f"Command: {command}", file=sys.stderr)

        # Cleanup existing processes in debug or print mode
        if mode in ["debug", "print"]:
            cleanup_existing_processes(container_name, probe_id, interface)

        # Execute command
        result = execute_command(container_name, command, mode, probe_id)

        sys.exit(result.returncode)

    finally:
        # Release lock
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

if __name__ == '__main__':
    main()
