# Configuration Guide

Main file: `config.yml`

## Model

- `containers`: toolchain definitions (image name and build context)
- `probes`: physical debug probes (id, serial, interface, VID/PID)
- `targets`: target definitions (container mapping, mode-aware compatibility, transport policy, command templates)
- `interface_defaults`: fallback commands per interface (for cross-target reuse)
- `ports`: base ports for GDB/Telnet/RTT allocation

## Add a new probe

1. Discover USB metadata:

```bash
lsusb
udevadm info -q property /dev/bus/usb/<BUS>/<DEV> | grep SERIAL
```

2. Add probe entry:

```yaml
probes:
  - id: 5
    name: "NXP LPC-Link2"
    serial: "0240000034544e45001e0016e2f3000a4eb1000097969900"
    vendor_id: "0d28"
    product_id: "0204"
    interface: cmsis-dap
```

Note:
- `interface` must match `targets.<target>.compatible_probes` (list or mode map) and target/default commands.
- Example: for ESP32-S3 built-in USB-JTAG, use `interface: esp-usb-jtag`.

USB-UART probe example:

```yaml
probes:
  - id: 10
    name: "USB-UART Adapter #1"
    serial: "A6001234"
    vendor_id: "0403"
    product_id: "6001"
    interface: usb-uart
    # Optional override. If omitted, defaults to /dev/probes/tty_probe_10
    # device_path: "/dev/probes/tty_probe_10"
```

For `interface: usb-uart`, udev rules generator also creates:
- `/dev/probes/tty_probe_<id>`

3. Regenerate udev rules:

```bash
python3 generate_udev_rules.py
sudo cp 99-debug-probe-hub.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Add a new target

```yaml
targets:
  my_mcu:
    container:
      jlink: jlink
      cmsis-dap: cmsis_dap
      usb-uart: uart
    description: "My Custom MCU"
    compatible_probes:
      debug: [jlink, cmsis-dap]
      flash: [jlink, cmsis-dap]
      print: [usb-uart]
    transports:
      jlink:
        default: swd
        allowed: [swd, jtag]
      cmsis-dap:
        default: swd
        allowed: [swd]
    commands:
      jlink:
        debug: "openocd -f interface/jlink.cfg -c 'transport select {transport}' -f target/mymcu.cfg -c 'jlink serial {serial}' -c 'gdb_port {gdb_port}'"
        flash: "openocd -f interface/jlink.cfg -c 'transport select {transport}' -f target/mymcu.cfg -c 'jlink serial {serial}' -c 'program {firmware_path} verify reset exit'"
      cmsis-dap:
        debug: "openocd -f interface/cmsis-dap.cfg -c 'transport select {transport}' -f target/mymcu.cfg -c 'adapter serial {serial}' -c 'gdb_port {gdb_port}'"
        flash: "openocd -f interface/cmsis-dap.cfg -c 'transport select {transport}' -f target/mymcu.cfg -c 'adapter serial {serial}' -c 'program {firmware_path} verify reset exit'"
```

WCH-Link target example:

```yaml
targets:
  ch32v203:
    container:
      wch-link: wch
      usb-uart: uart
    compatible_probes:
      debug: [wch-link]
      flash: [wch-link]
      print: [wch-link, usb-uart]
    transports:
      wch-link:
        default: sdi
        allowed: [sdi]
    commands:
      wch-link:
        flash: "openocd -f /opt/wch-toolchain/OpenOCD/OpenOCD/bin/wch-riscv.cfg -c 'adapter serial {serial}' -c 'program {firmware_path} verify reset exit'"
        debug: "openocd -f /opt/wch-toolchain/OpenOCD/OpenOCD/bin/wch-riscv.cfg -c 'adapter serial {serial}' -c 'gdb_port {gdb_port}' -c 'telnet_port {telnet_port}' -c 'bindto 0.0.0.0'"
```

For WCH RISC-V (`wch-riscv.cfg`), OpenOCD transport is effectively fixed to `sdi`.
WCH-Link ARM mode (USB PID `8012`) is separate and typically uses `swd`/`jtag` in ARM target policies.

## Interface defaults (shared fallback commands)

If `targets.<target>.commands.<interface>.<mode>` is missing, the loader checks
`interface_defaults.<interface>.commands.<mode>`.

Example (`usb-uart` print fallback for all targets):

```yaml
interface_defaults:
  usb-uart:
    commands:
      print: "socat TCP-LISTEN:{print_port},reuseaddr,fork,bind=0.0.0.0 FILE:{device_path},raw,echo=0,b{uart_baud}"
```

## Add a new interface type and toolchain container

1. Create a container image under `docker/<tool>/Dockerfile`.
2. Add container metadata in `config.yml` under `containers` (name/image_name/build_context).
3. Define probe(s) with new `interface`.
4. Define target commands under `targets.<target>.commands.<interface>`.
   If the command is cross-target common, prefer `interface_defaults.<interface>.commands.<mode>`.
5. Regenerate `docker-compose.probes.yml`:

```bash
python3 generate_docker_compose_probes.py --output docker-compose.probes.yml
```

## Placeholder variables in command templates

- `{serial}`
- `{gdb_port}`
- `{telnet_port}`
- `{rtt_port}`
- `{print_port}`
- `{firmware_path}`
- `{device_path}` (for serial-style devices where used)
- `{transport}` (if you want client-selected SWD/JTAG/etc)
- `{uart_baud}` (for UART print bridge command templates)

## ID and concurrency notes

- `probe.id` should be unique integer.
- Locking is based on `probe.id` (`/var/lock/probe_{id}.lock`).
- Routing is based on target compatibility + probe interface + serial-aware command templates.
- Compatibility can be mode-aware via `targets.<target>.compatible_probes.<mode>`.
- Transport is resolved per target/interface using `targets.<target>.transports.<interface>`.
- Client-specified `transport` is validated against `targets.<target>.transports.<interface>.allowed`.
- If client does not specify `transport`, `targets.<target>.transports.<interface>.default` is used.
- Container name used at runtime is `${containers.<key>.name}-p<probe_id>` (example: `debug-box-jlink-p1`).
- Compose generation creates only compatible `(container, probe)` pairs derived from `targets.*.container` and the union of `targets.*.compatible_probes` (all modes when mode map is used).
- Runtime containers are started lazily on first `/dispatch`.
