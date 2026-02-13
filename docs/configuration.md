# Configuration Guide

Main file: `config.yml`

## Model

- `containers`: toolchain definitions (image name and build context)
- `probes`: physical debug probes (id, serial, interface, VID/PID)
- `targets`: target definitions (container or per-interface container map, compatible interfaces, command templates)
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
- `interface` must match `targets.<target>.compatible_probes` and `targets.<target>.commands.<interface>`.
- Example: for ESP32-S3 built-in USB-JTAG, use `interface: esp-usb-jtag`.

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
    description: "My Custom MCU"
    compatible_probes: [jlink, cmsis-dap]
    commands:
      jlink:
        debug: "JLinkGDBServer -device MyMCU -if SWD -port {gdb_port} -select USB={serial}"
        flash: "JLinkExe -CommandFile /tmp/flash_my_mcu.jlink"
      cmsis-dap:
        debug: "openocd -f interface/cmsis-dap.cfg -f target/mymcu.cfg -c 'adapter serial {serial}' -c 'gdb_port {gdb_port}'"
        flash: "openocd -f interface/cmsis-dap.cfg -f target/mymcu.cfg -c 'adapter serial {serial}' -c 'program {firmware_path} verify reset exit'"
```

## Add a new interface type and toolchain container

1. Create a container image under `docker/<tool>/Dockerfile`.
2. Add container metadata in `config.yml` under `containers` (name/image_name/build_context).
3. Define probe(s) with new `interface`.
4. Define target commands under `targets.<target>.commands.<interface>`.
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

## ID and concurrency notes

- `probe.id` should be unique integer.
- Locking is based on `probe.id` (`/var/lock/probe_{id}.lock`).
- Routing is based on target compatibility + probe interface + serial-aware command templates.
- Container name used at runtime is `${containers.<key>.name}-p<probe_id>` (example: `debug-box-jlink-p1`).
- Compose generation creates only compatible `(container, probe)` pairs derived from `targets.*.container` and `targets.*.compatible_probes`.
- Runtime containers are started lazily on first `/dispatch`.
