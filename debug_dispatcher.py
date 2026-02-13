#!/usr/bin/env python3
"""
Debug Dispatcher
Executes debug or flash commands based on configuration
"""
import sys
import subprocess
import fcntl
import os
import time
import shutil
from pathlib import Path
from config_loader import get_config

PROCESS_STARTUP_GRACE_SECONDS = 10
FIRST_ATTACH_GRACE_SECONDS = 60
POLL_INTERVAL_SECONDS = 1
MAX_PROCESS_MISS_COUNT = 3


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

def probe_session_patterns(probe_id, mode):
    """Get process patterns that indicate an active probe session."""
    gdb_port = get_gdb_port(probe_id)
    rtt_port = get_rtt_port(probe_id)

    if mode == "debug":
        return [
            f"gdb_port {gdb_port}",
            f"-port {gdb_port}",
            f":{gdb_port}",
        ]
    if mode == "print":
        return [
            f"RTTTelnetPort {rtt_port}",
            f"TCP-LISTEN:{rtt_port}",
            f":{rtt_port}",
        ]
    return []

def has_active_session(container_name, probe_id, mode):
    """Check whether probe session process is still active in container."""
    patterns = probe_session_patterns(probe_id, mode)
    for pattern in patterns:
        result = subprocess.run(
            ["docker", "exec", container_name, "pgrep", "-f", "--", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if result.returncode == 0:
            return True
    return False

def monitor_log(probe_id, message):
    """Append lock-monitor lifecycle logs per probe."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    log_path = Path(f"/tmp/lock_monitor_probe_{probe_id}.log")
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Keep monitor robust even if logging fails.
        pass


def count_gdb_clients(gdb_port):
    """
    Count established TCP clients to local GDB server port using `ss`.

    Returns:
        int: number of ESTABLISHED sessions
        None: when `ss` is unavailable or check failed
    """
    if not shutil.which("ss"):
        return None

    try:
        result = subprocess.run(
            ["ss", "-H", "-tan", "state", "established", f"sport = :{gdb_port}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None

    if result.returncode != 0 and not result.stdout.strip():
        return 0

    return len([line for line in result.stdout.splitlines() if line.strip()])


def run_lock_monitor(lock_fd, container_name, probe_id, mode, interface):
    """Keep lock held while session is active; debug mode is client-connection based."""
    lock_file = os.fdopen(lock_fd, 'w')
    seen_process = False
    miss_count = 0
    started_at = time.time()
    gdb_port = get_gdb_port(probe_id)
    saw_client = False
    ss_available = bool(shutil.which("ss"))

    if mode == "debug":
        monitor_log(
            probe_id,
            f"startup: waiting for first GDB attach up to {FIRST_ATTACH_GRACE_SECONDS}s (container={container_name}, port={gdb_port})",
        )
        if not ss_available:
            monitor_log(
                probe_id,
                "warning: `ss` not found; falling back to process-liveness mode (auto-disconnect cleanup disabled)",
            )

    try:
        while True:
            active = has_active_session(container_name, probe_id, mode)
            if active:
                seen_process = True
                miss_count = 0
            else:
                if (not seen_process) and (time.time() - started_at < PROCESS_STARTUP_GRACE_SECONDS):
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                miss_count += 1
                if miss_count >= MAX_PROCESS_MISS_COUNT:
                    monitor_log(probe_id, f"session process missing repeatedly; ending monitor (mode={mode})")
                    break

            if mode == "debug" and ss_available:
                client_count = count_gdb_clients(gdb_port)
                if client_count is None:
                    ss_available = False
                    monitor_log(
                        probe_id,
                        "warning: failed to read GDB client state via `ss`; falling back to process-liveness mode",
                    )
                elif client_count > 0:
                    if not saw_client:
                        saw_client = True
                        monitor_log(probe_id, f"first GDB attach detected (clients={client_count})")
                else:
                    elapsed = time.time() - started_at
                    if saw_client:
                        monitor_log(probe_id, "GDB disconnect detected; stopping debug session")
                        cleanup_existing_processes(container_name, probe_id, interface)
                        break
                    if elapsed >= FIRST_ATTACH_GRACE_SECONDS:
                        monitor_log(
                            probe_id,
                            f"no GDB attach within {FIRST_ATTACH_GRACE_SECONDS}s; stopping debug session",
                        )
                        cleanup_existing_processes(container_name, probe_id, interface)
                        break

            time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        monitor_log(probe_id, "unlock complete; lock monitor exiting")
        lock_file.close()

def start_lock_monitor(lock_file, container_name, probe_id, mode, interface):
    """Spawn background monitor process that inherits the lock FD."""
    lock_fd = lock_file.fileno()
    script_path = Path(__file__).resolve()
    subprocess.Popen(
        [
            sys.executable,
            str(script_path),
            "--lock-monitor",
            str(lock_fd),
            container_name,
            str(probe_id),
            mode,
            interface,
        ],
        pass_fds=[lock_fd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

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
    subprocess.run(
        ["docker", "exec", container_name, "pkill", "-f", f"Starting print server (probe {probe_id})"],
        stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["docker", "exec", container_name, "pkill", "openocd"],
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
            ["docker", "exec", container_name, "pkill", "wlink"],
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["docker", "exec", container_name, "pkill", "socat"],
            stderr=subprocess.DEVNULL
        )

def run_compose(compose_args, **kwargs):
    """Run docker compose command with docker-compose/docker compose fallback."""
    candidates = [
        ["docker-compose"],
        ["docker", "compose"],
    ]
    for prefix in candidates:
        try:
            return subprocess.run(prefix + compose_args, **kwargs)
        except FileNotFoundError:
            continue
    raise FileNotFoundError("docker-compose (or docker compose plugin) is not installed")

def ensure_container_running(container_name):
    """Start target container on demand if it is not running yet."""
    compose_path = Path(__file__).resolve().parent / "docker-compose.probes.yml"
    if not compose_path.exists():
        print(
            f"Error: Compose file not found: {compose_path}. "
            "Run generate_docker_compose_probes.py first.",
            file=sys.stderr,
        )
        return False

    try:
        result = run_compose(
            ["-f", str(compose_path), "up", "-d", container_name],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(
            f"Error: Failed to start container {container_name}:\n"
            f"{result.stdout}{result.stderr}",
            file=sys.stderr,
        )
        return False
    return True

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

def maybe_run_lock_monitor():
    """Internal entrypoint for lock monitor subprocess."""
    if len(sys.argv) >= 2 and sys.argv[1] == "--lock-monitor":
        if len(sys.argv) != 7:
            print(
                "Usage: debug_dispatcher.py --lock-monitor <lock_fd> <container> <probe_id> <mode> <interface>",
                file=sys.stderr,
            )
            sys.exit(2)

        lock_fd = int(sys.argv[2])
        container_name = sys.argv[3]
        probe_id = int(sys.argv[4])
        mode = sys.argv[5]
        interface = sys.argv[6]
        run_lock_monitor(lock_fd, container_name, probe_id, mode, interface)
        sys.exit(0)

def main():
    maybe_run_lock_monitor()

    if len(sys.argv) < 4:
        print(
            "Usage: debug_dispatcher.py <target> <probe_id> <mode> [firmware_file] [transport]",
            file=sys.stderr,
        )
        sys.exit(1)

    target_name = sys.argv[1]
    probe_id = int(sys.argv[2])
    mode = sys.argv[3]
    firmware_file = sys.argv[4] if len(sys.argv) > 4 else ""
    requested_transport = sys.argv[5] if len(sys.argv) > 5 else ""

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

    interface = probe['interface']
    try:
        transport = config.resolve_transport(
            target_name=target_name,
            interface=interface,
            requested_transport=requested_transport,
            mode=mode,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Get base container for target and resolve per-probe container instance.
    # We run one container instance per (toolchain container) x (probe_id).
    base_container_name = config.get_container_for_target(target_name, interface=interface)
    if not base_container_name:
        print(
            f"Error: No container configured for target {target_name} (interface={interface})",
            file=sys.stderr,
        )
        sys.exit(1)
    container_name = f"{base_container_name}-p{probe_id}"

    # Acquire lock
    lock_file = acquire_lock(probe_id)
    lock_transferred = False

    try:
        if not ensure_container_running(container_name):
            sys.exit(1)

        # Get command template
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
            transport=transport or "",
            device_path=device_path,
            firmware_path=firmware_path
        )

        print(f"Target: {target_name}", file=sys.stderr)
        print(f"Probe: {probe['name']} (ID: {probe_id})", file=sys.stderr)
        print(f"Mode: {mode}", file=sys.stderr)
        if transport:
            print(f"Transport: {transport}", file=sys.stderr)
        print(f"Container: {container_name}", file=sys.stderr)
        print(f"Command: {command}", file=sys.stderr)

        # Cleanup existing processes in debug or print mode
        if mode in ["debug", "print"]:
            cleanup_existing_processes(container_name, probe_id, interface)

        # Execute command
        result = execute_command(container_name, command, mode, probe_id)
        if mode in ["debug", "print"] and result.returncode == 0:
            start_lock_monitor(lock_file, container_name, probe_id, mode, interface)
            lock_transferred = True

        sys.exit(result.returncode)

    finally:
        # Release lock unless it was transferred to monitor process.
        if not lock_transferred:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

if __name__ == '__main__':
    main()
