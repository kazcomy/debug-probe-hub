# Debug Probe Hub - Proxmox Deployment Guide

This guide explains how to deploy Debug Probe Hub on a Proxmox Ubuntu VM using Cloud-init.

## Overview

The deployment uses Cloud-init to automatically configure a fresh Ubuntu VM with:
- Static IP address (192.168.1.234)
- Docker and Docker Compose
- Debug Probe Hub installation
- systemd service for automatic startup

## Prerequisites

1. **Proxmox VE** server
2. **Ubuntu Cloud Image** (24.04 LTS recommended, 22.04 LTS also supported)
   - **24.04 LTS**: https://cloud-images.ubuntu.com/releases/24.04/release/
   - **22.04 LTS**: https://cloud-images.ubuntu.com/releases/22.04/release/
   - Use the `.img` file (e.g., `ubuntu-24.04-server-cloudimg-amd64.img`)
   - 24.04 LTS is recommended for longer support (until 2034) and newer packages
3. **USB Debug Probes** physically connected to the Proxmox host

## Quick Start (TL;DR)

For the impatient, here's the minimal command sequence:

```bash
# On Proxmox host
# 1. Upload cloud-init files to /var/lib/vz/snippets/
# 2. Download Ubuntu image
cd /var/lib/vz/template/iso
wget https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img

# 3. Create VM with cloud-init
qm create 100 --name debug-probe-hub --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk 100 ubuntu-24.04-server-cloudimg-amd64.img local-lvm
qm set 100 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-100-disk-0 --boot c --bootdisk scsi0
qm set 100 --ide2 local-lvm:cloudinit
qm set 100 --cicustom "user=local:snippets/debug-probe-hub-user.yml,network=local:snippets/debug-probe-hub-network.yml"

# 4. Add USB devices (check with lsusb)
qm set 100 --usb0 host=1366:0105  # Your J-Link VID:PID

# 5. Start and wait 3-5 minutes
qm start 100
```

See detailed steps below for full explanation.

## Detailed Setup

### Step 1: Prepare Cloud-init Configuration

1. Copy templates and customize:
   ```bash
   cd deploy
   cp cloud-init-user-data.template.yml cloud-init-user-data.yml
   cp cloud-init-network.template.yml cloud-init-network.yml
   ```

2. Edit the files and replace all `TODO` placeholders:
   - `cloud-init-user-data.yml`: Username, SSH public key, GitHub username, timezone
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
# scp deploy/cloud-init-user-data.yml root@proxmox:/var/lib/vz/snippets/debug-probe-hub-user.yml
# scp deploy/cloud-init-network.yml root@proxmox:/var/lib/vz/snippets/debug-probe-hub-network.yml

# Option 2: Create directly on Proxmox
nano /var/lib/vz/snippets/debug-probe-hub-user.yml
nano /var/lib/vz/snippets/debug-probe-hub-network.yml

# === Step 2: Download Ubuntu cloud image ===
cd /var/lib/vz/template/iso
wget https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img

# === Step 3: Create and configure VM ===
# Variables
VM_ID=100
VM_NAME="debug-probe-hub"
CLOUD_IMAGE="/var/lib/vz/template/iso/ubuntu-24.04-server-cloudimg-amd64.img"

# Create VM
qm create $VM_ID --name $VM_NAME --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0

# Import disk
qm importdisk $VM_ID $CLOUD_IMAGE local-lvm

# Attach disk
qm set $VM_ID --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-$VM_ID-disk-0

# Make disk bootable
qm set $VM_ID --boot c --bootdisk scsi0

# Add Cloud-init drive
qm set $VM_ID --ide2 local-lvm:cloudinit

# Configure Cloud-init with custom snippets
qm set $VM_ID --cicustom "user=local:snippets/debug-probe-hub-user.yml,network=local:snippets/debug-probe-hub-network.yml"

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

### Step 3: Verify Deployment

Wait 3-5 minutes for cloud-init to complete, then:

```bash
# SSH into the VM (use your username, not 'debug')
ssh kazcomy@192.168.1.234

# Check service status
systemctl status debug-probe-hub

# Check Docker containers
docker ps

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
# SSH into VM
ssh debug@192.168.1.234

# Pull latest changes
cd /opt/debug-probe-hub
git pull

# Restart service
sudo systemctl restart debug-probe-hub
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
