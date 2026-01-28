# Debug Probe Hub

A unified debugging and firmware flashing hub for multiple microcontroller targets and debug probes.

## Overview

Debug Probe Hub provides a centralized HTTP API to manage firmware flashing and debugging sessions across multiple debug probes and target devices. All configuration is centralized in `config.yml`, making it easy to add new probes or targets.

## Features

- **Configuration-driven**: All settings in one YAML file
- **Multiple targets**: nRF52840, ESP32-S3, STM32G3, CH32V series
- **Multiple probes**: J-Link, CMSIS-DAP, WCH-Link
- **Docker-based**: Isolated toolchains for each target family
- **REST API**: Simple HTTP interface for remote operations
- **Auto-generated udev rules**: Consistent device naming

## Architecture

```
┌─────────────────┐
│  HTTP Server    │ (server.py)
│  Port 8080      │
└────────┬────────┘
         │
         ├─→ probe_status.py (check probe connections)
         │
         └─→ debug_dispatcher.py
                    │
                    ├─→ Docker: debug-box-std (OpenOCD, J-Link)
                    ├─→ Docker: debug-box-esp (OpenOCD-ESP32)
                    └─→ Docker: debug-box-wch (minichlink)
```

## File Structure

```
debug-probe-hub/
├── config.yml                  # Main configuration file
├── config_loader.py            # Configuration parser library
├── server.py                   # HTTP API server
├── debug_dispatcher.py         # Command execution logic
├── probe_status.py             # Probe status checker
├── probe_finder.py             # Probe search utility
├── generate_udev_rules.py      # udev rules generator
├── setup.sh                    # Setup script
├── pyproject.toml              # Python project metadata
├── LICENSE                     # MIT License
├── docker-compose.yml          # Container orchestration
└── docker/
    ├── standard/Dockerfile     # Standard ARM tools
    ├── esp32/Dockerfile        # ESP32 tools
    └── wch/Dockerfile          # WCH RISC-V tools
```

## Setup

### Prerequisites

- Linux host (tested on Ubuntu 22.04)
- Docker and Docker Compose
- Python 3.8+
- Root access (for udev rules)

### Installation

1. Clone or extract this repository

2. Review and customize `config.yml`:
   - Update probe serial numbers
   - Adjust vendor/product IDs if needed
   - Add or remove targets as needed

3. Run setup script:
```bash
./setup.sh
```

This will:
- Install Python dependencies
- Generate and install udev rules
- Build Docker images
- Create working directories

4. Connect your debug probes and verify:
```bash
ls -l /dev/probes/
```

You should see symlinks like `probe_1`, `probe_2`, etc.

### Manual Setup

If you prefer manual setup:

```bash
# Install dependencies
pip3 install pyyaml

# Generate udev rules
python3 generate_udev_rules.py
sudo cp 99-debugger-station.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Build containers
docker-compose build

# Start containers
docker-compose up -d

# Start server
python3 server.py
```

## Usage

### Start the System

```bash
# Start Docker containers
docker-compose up -d

# Start HTTP server (in another terminal or as a service)
python3 server.py
```

### API Endpoints

#### GET /status
Check status of all probes

```bash
curl http://localhost:8080/status
```

Response:
```json
[
  {
    "id": 1,
    "name": "Segger J-Link",
    "status": "connected",
    "serial": "000051025665",
    "expected_serial": "000051025665",
    "match": true
  },
  ...
]
```

#### GET /probes
List all configured probes

```bash
curl http://localhost:8080/probes
```

#### GET /probes/search
Search for probes by interface, VID/PID, serial, or name

This endpoint allows clients to find probes without knowing internal probe IDs. Clients only need to know physical identifiers like interface type, VID/PID, or serial numbers.

**Query Parameters:**
- `interface` - Interface type (e.g., "jlink", "cmsis-dap", "wch-link")
- `vid` or `vendor_id` - USB Vendor ID (e.g., "1366" or "0x1366")
- `pid` or `product_id` - USB Product ID (e.g., "0105")
- `serial` - Serial number (for disambiguation when multiple probes of same type)
- `name` - Partial name match (e.g., "J-Link")

**Examples:**

Find all J-Link probes:
```bash
curl "http://localhost:8080/probes/search?interface=jlink"
```

Find probe by VID/PID:
```bash
curl "http://localhost:8080/probes/search?vid=1366&pid=0105"
```

Find specific probe by serial (when you have multiple of same type):
```bash
curl "http://localhost:8080/probes/search?interface=jlink&serial=000051025665"
```

Find by name:
```bash
curl "http://localhost:8080/probes/search?name=WCH-Link"
```

**Response:**
```json
{
  "query": {
    "interface": "jlink",
    "vendor_id": null,
    "product_id": null,
    "serial": null,
    "name": null
  },
  "matches": [
    {
      "id": 1,
      "name": "Segger J-Link",
      "serial": "000051025665",
      "vendor_id": "1366",
      "product_id": "0105",
      "interface": "jlink"
    }
  ],
  "count": 1
}
```

**Using probe search in dispatch:**

Instead of hardcoding probe IDs, clients can search first:
```bash
# 1. Find the probe
PROBE_ID=$(curl -s "http://localhost:8080/probes/search?interface=jlink" | jq -r '.matches[0].id')

# 2. Use it for flashing
curl -X POST http://localhost:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=$PROBE_ID" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

#### GET /targets
List all supported targets

```bash
curl http://localhost:8080/targets
```

#### POST /dispatch
Flash firmware or start debug session

Flash firmware:
```bash
curl -X POST http://localhost:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=1" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

Start debug session:
```bash
curl -X POST http://localhost:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=1" \
  -F "mode=debug"
```

Then connect GDB:
```bash
arm-none-eabi-gdb -ex "target remote localhost:3331"
```

## Common Usage Patterns

### Example 1: Flash firmware without knowing probe ID

```bash
# Find any available J-Link probe
PROBE_ID=$(curl -s "http://localhost:8080/probes/search?interface=jlink" | jq -r '.matches[0].id')

# Flash firmware
curl -X POST http://localhost:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=$PROBE_ID" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

### Example 2: Use specific probe when multiple are connected

```bash
# You have 2 CMSIS-DAP probes, use the one with specific serial
PROBE_ID=$(curl -s "http://localhost:8080/probes/search?interface=cmsis-dap&serial=C2428F064718" | jq -r '.matches[0].id')

curl -X POST http://localhost:8080/dispatch \
  -F "target=stm32g3" \
  -F "probe=$PROBE_ID" \
  -F "mode=debug"
```

### Example 3: Command-line probe search tool

```bash
# Search by interface
python3 probe_finder.py --interface jlink

# Search by VID/PID
python3 probe_finder.py --vendor-id 1366 --product-id 0105

# Search by name
python3 probe_finder.py --name "WCH-Link"

# Combined search with JSON output
python3 probe_finder.py --interface cmsis-dap --serial C2428F064718 --json
```

## Configuration

### Adding a New Probe

Edit `config.yml` and add to the `probes` section:

```yaml
probes:
  - id: 5
    name: "My New Probe"
    serial: "ABCD1234"
    vendor_id: "1234"
    product_id: "5678"
    interface: cmsis-dap
```

Then regenerate udev rules:
```bash
python3 generate_udev_rules.py
sudo cp 99-debugger-station.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Adding a New Target

Edit `config.yml` and add to the `targets` section:

```yaml
targets:
  my_mcu:
    container: standard
    description: "My Custom MCU"
    compatible_probes: [1, 2, 3]
    commands:
      jlink:
        debug: "JLinkGDBServer -device MyMCU -if SWD -port {gdb_port}"
        flash: "JLinkExe -CommandFile /tmp/flash.jlink"
      cmsis-dap:
        debug: "openocd -f interface/cmsis-dap.cfg -f target/mymcu.cfg ..."
        flash: "openocd ... -c 'program {firmware_path} verify reset exit'"
```

### Command Templates

Command templates support the following placeholders:
- `{serial}` - Probe serial number
- `{gdb_port}` - GDB server port (base + probe_id)
- `{telnet_port}` - Telnet port (base + probe_id)
- `{firmware_path}` - Path to firmware file in container

## Troubleshooting

### Probes not detected

Check udev rules:
```bash
ls -l /dev/probes/
sudo udevadm info /dev/probes/probe_1
```

### Docker container issues

Check container logs:
```bash
docker-compose logs debug-box-std
```

Verify container is running:
```bash
docker ps
```

### Permission issues

Ensure your user is in the dialout group:
```bash
sudo usermod -a -G dialout $USER
```

Log out and back in for changes to take effect.

### Port conflicts

If GDB ports conflict, adjust `ports.gdb_base` in `config.yml`.

## Development

### Running Tests

```bash
# Test probe status
python3 probe_status.py

# Test configuration loading
python3 -c "from config_loader import get_config; print(get_config().get_all_probes())"

# Test dispatcher (requires running containers)
python3 debug_dispatcher.py nrf52840 1 debug
```

### Adding New Features

The modular design makes it easy to extend:

1. **config_loader.py**: Add helper methods for new config sections
2. **server.py**: Add new API endpoints
3. **debug_dispatcher.py**: Add new execution modes
4. **config.yml**: Add new targets, probes, or containers

## Installation

### Using pip (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/debug-probe-hub.git
cd debug-probe-hub

# Install with dependencies
pip install -e .

# Or install from PyPI (when published)
pip install debug-probe-hub
```

### Manual Installation

Follow the setup instructions in the "Setup" section above.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenOCD](https://openocd.org/) - Open On-Chip Debugger
- [Espressif ESP-IDF](https://github.com/espressif/esp-idf) - ESP32 development framework
- [Segger J-Link](https://www.segger.com/products/debug-probes/j-link/) - Professional debug probes
- [WCH minichlink](https://github.com/cnlohr/ch32v003fun) - WCH RISC-V debug tools

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues or questions, please check:
1. This README
2. Generated udev rules: `99-debug-probe-hub.rules`
3. Container logs: `docker-compose logs`
4. Server logs: Check stderr output from `server.py`
5. [GitHub Issues](https://github.com/yourusername/debug-probe-hub/issues)
