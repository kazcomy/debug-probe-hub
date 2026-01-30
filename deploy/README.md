# Debug Probe Hub - Proxmox Deployment Guide

This guide explains how to deploy Debug Probe Hub on a Proxmox Ubuntu VM using Cloud-init.

## Quick Start Summary

```
1. Modify template to prepare cloud-init config files (cloud-init-user-data.yml, cloud-init-network.yml)
2. Create Proxmox VM with cloud-init and USB passthrough
3. Start VM → cloud-init installs Docker, dependencies, clones repo (STOPS HERE)
4. SSH in → Modify tempalate to prepare docker-compose.override.yml with GitHub token
5. Run: sudo systemctl start debug-probe-hub-setup (builds Docker images)
6. Run: sudo systemctl start debug-probe-hub (starts server)
7. Test: curl http://localhost:8080/status
```

**Key Point:** The VM intentionally stops after initial cloud-init setup. You must manually configure WCH toolchain access before building Docker images.

## Overview

The deployment uses Cloud-init to automatically configure a fresh Ubuntu VM in **two phases**:

### Phase 1: Automated Pre-Setup (cloud-init)
When you first start the VM, cloud-init automatically runs and installs:
- Static IP address (192.168.1.234)
- Docker and Docker Compose
- Python dependencies
- Debug Probe Hub repository
- udev rules for USB probes
- systemd services (enabled but not started)

**IMPORTANT:** The VM will stop after Phase 1. This is intentional - you need to configure WCH toolchain access before building Docker images.

### Phase 2: Manual Docker Build and Startup
After cloud-init completes, you manually:
1. Configure `docker-compose.override.yml` with GitHub token (for WCH toolchain access)
2. Run `systemctl start debug-probe-hub-setup` to build Docker images
3. Run `systemctl start debug-probe-hub` to start the server

## Prerequisites

1. **Proxmox VE** server
2. **Ubuntu Cloud Image** (24.04 LTS recommended, 22.04 LTS also supported)
   - **24.04 LTS**: https://cloud-images.ubuntu.com/releases/24.04/release/
   - **22.04 LTS**: https://cloud-images.ubuntu.com/releases/22.04/release/
   - Use the `.img` file (e.g., `ubuntu-24.04-server-cloudimg-amd64.img`)
   - 24.04 LTS is recommended for longer support (until 2034) and newer packages
3. **USB Debug Probes** physically connected to the Proxmox host

## Detailed Setup

### Step 1: Prepare Cloud-init Configuration

1. Copy templates and customize:
   ```bash
   cd deploy
   cp cloud-init-user-data.template.yml cloud-init-user-data.yml
   cp cloud-init-network.template.yml cloud-init-network.yml
   ```

2. Edit the files and replace all `TODO` placeholders:
   - `cloud-init-user-data.yml`: Username, password, GitHub username, timezone
   - `cloud-init-network.yml`: IP address, gateway, DNS servers, interface name

   Note: These files are gitignored and won't be committed.

### Step 2: Create VM in Proxmox (Command Line)

```bash
# On Proxmox host

# === Step 1: Prepare Cloud-init files ===
# Copy your edited cloud-init files to snippets directory
cd /var/lib/vz/snippets

# Option 1: Upload from your local machine
# (From your local machine)
# scp deploy/cloud-init-user-data.yml root@proxmox:/var/lib/vz/snippets/
# scp deploy/cloud-init-network.yml root@proxmox:/var/lib/vz/snippets/

# Option 2: Create directly on Proxmox
nano /var/lib/vz/snippets/cloud-init-user-data.yml
nano /var/lib/vz/snippets/cloud-init-network.yml

# === Step 2: Download Ubuntu cloud image ===
cd /var/lib/vz/template/iso
wget https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img

# === Step 3: Create and configure VM ===
#!/bin/bash

# Variables
VM_ID=100
VM_NAME="debug-probe-hub"
CLOUD_IMAGE="/var/lib/vz/template/iso/noble-server-cloudimg-amd64.img"
STORAGE="local-lvm"
# 1. Create VM
qm create $VM_ID --name $VM_NAME --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0

# 2. Import disk
qm importdisk $VM_ID $CLOUD_IMAGE $STORAGE

# 3. Attach disk
qm set $VM_ID --scsihw virtio-scsi-pci --scsi0 $STORAGE:vm-$VM_ID-disk-0

# 4. Resize disk
qm resize $VM_ID scsi0 100G

# 5. Make it bootable
qm set $VM_ID --boot c --bootdisk scsi0

# 6. Add Cloud-init drive
qm set $VM_ID --ide2 $STORAGE:cloudinit

# 7. Configure Cloud-init with custom snippets
qm set $VM_ID --cicustom "user=local:snippets/cloud-init-user-data.yml,network=local:snippets/cloud-init-network.yml"

# (Optional) Apply configuration and generate image
qm cloudinit update $VM_ID

# === Step 4: Add USB devices ===
# Find your USB devices first
lsusb

# Add USB device by vendor:product ID (recommended - survives reconnects)
# Example for J-Link (1366:0105)
qm set $VM_ID --usb0 host=1366:0105

# Add more USB devices as needed
# qm set $VM_ID --usb1 host=1a86:8010  # WCH-Link #1
# qm set $VM_ID --usb2 host=1a86:8010  # WCH-Link #2

# === Step 5: Start VM ===
qm start $VM_ID

# === Step 6: Monitor cloud-init progress ===
# Wait 3-5 minutes for cloud-init to complete
# Check VM console or SSH in:
# ssh kazcomy@192.168.1.234

# Check cloud-init status
# cloud-init status
# tail -f /var/log/cloud-init-output.log
```

### Step 3: Post-Installation Setup (After cloud-init Completes)

**Wait 3-5 minutes** for cloud-init pre-setup to complete. The VM will be ready when you can SSH in.

```bash
# SSH into the VM (use your configured username)
ssh YOUR_USERNAME@192.168.1.234

# Check pre-setup completion
cloud-init status
# Expected output: status: done

# Verify Docker is installed
docker --version
docker-compose --version
```

#### Configure WCH Toolchain Access (REQUIRED)

The WCH container requires private repository access. **You must configure this before building Docker images.**

```bash
# Navigate to debug-probe-hub directory
cd /opt/debug-probe-hub

# Copy the docker-compose override template
cp docker-compose.override.yml.template docker-compose.override.yml

# Edit with your GitHub token
nano docker-compose.override.yml

# Replace YOUR_TOKEN with your actual GitHub Personal Access Token:
# services:
#   debug-box-wch:
#     build:
#       args:
#         WCH_TOOLCHAIN_URL: "https://YOUR_TOKEN@github.com/YOUR_ORG/wch-toolchain-mirror.git"
```

**How to get a GitHub token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope (for private repository access)
3. Copy the token and paste it into `docker-compose.override.yml`

#### Build Docker Images

```bash
# Start the setup service (builds all Docker images)
# This will take 10-20 minutes depending on network speed
sudo systemctl start debug-probe-hub-setup

# Monitor build progress
journalctl -u debug-probe-hub-setup -f

# Wait until you see "Build complete" message
```

#### Start Debug Probe Hub

```bash
# Start the main service
sudo systemctl start debug-probe-hub

# Verify service is running
systemctl status debug-probe-hub

# Check Docker containers
docker ps

# Test API
curl http://localhost:8080/status
```

### Step 4: Verify Deployment

After completing all setup steps:

```bash
# Check all services are running
systemctl status debug-probe-hub-pre-setup  # Should be: inactive (dead) - ran once
systemctl status debug-probe-hub-setup      # Should be: inactive (dead) - ran once
systemctl status debug-probe-hub            # Should be: active (running)

# Check Docker containers
docker ps
# Expected: debug-box-std, debug-box-esp, debug-box-wch all running

# Check if probes are detected
curl http://localhost:8080/status

# Check logs
journalctl -u debug-probe-hub -f
```

## Manual Installation (Without Cloud-init)

If you prefer manual installation:

1. **Install Ubuntu Server** (standard installation)

2. **Install system dependencies**:
   ```bash
   sudo bash install-system-deps.sh
   ```

3. **Clone repository**:
   ```bash
   git clone https://github.com/yourusername/debug-probe-hub.git /opt/debug-probe-hub
   cd /opt/debug-probe-hub
   ```

4. **Run setup**:
   ```bash
   sudo bash setup.sh
   ```

5. **Install systemd service**:
   ```bash
   sudo cp deploy/systemd/debug-probe-hub.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable debug-probe-hub
   sudo systemctl start debug-probe-hub
   ```

6. **Configure static IP** (edit `/etc/netplan/00-installer-config.yaml`):
   ```yaml
   network:
     version: 2
     ethernets:
       ens18:
         dhcp4: no
         addresses:
           - 192.168.1.234/24
         routes:
           - to: default
             via: 192.168.1.1
         nameservers:
           addresses: [8.8.8.8, 8.8.4.4]
   ```

   Apply: `sudo netplan apply`

## USB Passthrough Configuration

### Finding USB Device IDs

```bash
# On Proxmox host
lsusb

# Example output:
# Bus 001 Device 005: ID 1366:0105 SEGGER J-Link
# Bus 001 Device 006: ID 1a86:8010 QinHeng Electronics WCH-Link
```

### Add USB Device to VM

**Method 1: Vendor/Product ID** (Recommended - survives reconnects)
```bash
qm set 100 --usb0 host=1366:0105  # J-Link
qm set 100 --usb1 host=1a86:8010  # WCH-Link #1
qm set 100 --usb2 host=1a86:8010  # WCH-Link #2
```

**Method 2: USB Port** (Device-specific location)
```bash
qm set 100 --usb0 host=1-1.2
```

## Network Configuration

### Change Static IP

Edit `cloud-init-network.yml`:

```yaml
addresses:
  - 192.168.1.234/24  # Change this
routes:
  - to: default
    via: 192.168.1.1  # Change gateway
```

Or manually edit `/etc/netplan/` config on the VM.

### Firewall Configuration

If using Proxmox firewall:

1. Datacenter → Firewall → Add rule:
   - Direction: in
   - Action: ACCEPT
   - Protocol: tcp
   - Dest. port: 8080
   - Comment: Debug Probe Hub API

## Troubleshooting

### Cloud-init not running

```bash
# Check cloud-init status
cloud-init status

# View logs
cat /var/log/cloud-init.log
cat /var/log/cloud-init-output.log

# Re-run cloud-init (testing)
sudo cloud-init clean
sudo cloud-init init
```

### USB devices not visible

```bash
# In VM, check USB devices
lsusb

# Check udev rules
ls -l /dev/probes/

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Service not starting

```bash
# Check service status
systemctl status debug-probe-hub

# Check logs
journalctl -u debug-probe-hub -n 50

# Check Docker
docker ps
docker-compose logs
```

### Network not configured

```bash
# Check network interface name
ip a

# Edit cloud-init-network.yml to match your interface name
# Common names: ens18, eth0, enp0s3

# Apply netplan config manually
sudo netplan apply
```

## Updating Debug Probe Hub

```bash
# SSH into VM (use your username from cloud-init config)
ssh YOUR_USERNAME@192.168.1.234

# Pull latest changes
cd /opt/debug-probe-hub
git pull

# Rebuild Docker images if needed
sudo systemctl restart debug-probe-hub-setup.service

# Restart main service
sudo systemctl restart debug-probe-hub.service
```

## Advanced: Multiple Debug Stations

To deploy multiple debug stations, create multiple VMs with different:
- VM IDs (100, 101, 102...)
- Static IPs (192.168.1.234, 192.168.1.235...)
- USB device assignments

## Support

For issues:
- Check main [README.md](../README.md)
- Review logs: `journalctl -u debug-probe-hub`
- Test manually: `cd /opt/debug-probe-hub && python3 server.py`
