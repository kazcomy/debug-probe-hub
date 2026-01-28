#!/bin/bash
# Install system dependencies for Debug Probe Hub
# This script should be run with sudo on a fresh Ubuntu installation

set -e

echo "===================================="
echo "Debug Probe Hub - System Setup"
echo "===================================="

# Update package lists
echo ""
echo "Updating package lists..."
apt-get update

# Install essential packages
echo ""
echo "Installing essential packages..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3 \
    python3-pip \
    udev \
    usbutils

# Install Docker
echo ""
echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo "Docker installed successfully"
else
    echo "Docker already installed"
fi

# Enable Docker service
echo ""
echo "Enabling Docker service..."
systemctl enable docker
systemctl start docker

# Add current user to docker group (if not root)
if [ "$SUDO_USER" ]; then
    echo ""
    echo "Adding $SUDO_USER to docker group..."
    usermod -aG docker "$SUDO_USER"
    echo "Note: User needs to log out and back in for group changes to take effect"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install pyyaml

# Install jq (for JSON parsing in examples)
echo ""
echo "Installing additional utilities..."
apt-get install -y jq

echo ""
echo "===================================="
echo "System dependencies installed!"
echo "===================================="
echo ""
echo "Next steps:"
echo "  1. If you added a user to docker group, log out and back in"
echo "  2. Clone debug-probe-hub repository"
echo "  3. Run setup.sh in the repository"
