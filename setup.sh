#!/bin/bash
# Debugger Station Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "===================================="
echo "Debugger Station Setup"
echo "===================================="

# Check if config.yml exists
if [ ! -f "config.yml" ]; then
    echo "ERROR: config.yml not found!"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install pyyaml
else
    echo "WARNING: pip3 not found. Please install PyYAML manually:"
    echo "  pip3 install pyyaml"
fi

# Generate udev rules
echo ""
echo "Generating udev rules..."
python3 generate_udev_rules.py

# Install udev rules
echo ""
echo "Installing udev rules..."
if [ -f "99-debugger-station.rules" ]; then
    sudo cp 99-debugger-station.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "udev rules installed successfully"
else
    echo "ERROR: Failed to generate udev rules"
    exit 1
fi

# Create upload directory
echo ""
echo "Creating upload directory..."
sudo mkdir -p /tmp/flash_staging
sudo chmod 777 /tmp/flash_staging

# Make scripts executable
echo ""
echo "Making scripts executable..."
chmod +x generate_udev_rules.py
chmod +x server.py
chmod +x debug_dispatcher.py
chmod +x probe_status.py
chmod +x probe_finder.py

# Build Docker images
echo ""
echo "Building Docker images..."
docker-compose build

echo ""
echo "===================================="
echo "Setup Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "  1. Review and customize config.yml for your setup"
echo "  2. Start containers: docker-compose up -d"
echo "  3. Start server: python3 server.py"
echo "  4. Check probe status: curl http://localhost:8080/status"
echo "  5. Search for probes: python3 probe_finder.py --interface jlink"
echo ""
echo "For more information, see README.md"
