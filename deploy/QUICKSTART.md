# Debug Probe Hub - Quick Start Guide

This is a condensed guide for experienced users. For detailed explanations, see [README.md](README.md).

## Prerequisites

- Proxmox VE server
- SSH access to Proxmox host
- Your edited `cloud-init-user-data.yml` and `cloud-init-network.yml` files
  - **CRITICAL**: You MUST configure authentication (SSH key or password) in `cloud-init-user-data.yml` or you won't be able to login!

## One-Command Setup

```bash
# Run this on Proxmox host (adjust paths as needed)
bash <(cat <<'SETUP_SCRIPT'
#!/bin/bash
set -e

VM_ID=100
VM_NAME="debug-probe-hub"

# Download Ubuntu image
cd /var/lib/vz/template/iso
[ ! -f ubuntu-24.04-server-cloudimg-amd64.img ] && \
  wget https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img

# Create VM
qm create $VM_ID --name $VM_NAME --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk $VM_ID ubuntu-24.04-server-cloudimg-amd64.img local-lvm
qm set $VM_ID --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-$VM_ID-disk-0
qm set $VM_ID --boot c --bootdisk scsi0
qm set $VM_ID --ide2 local-lvm:cloudinit

# Configure cloud-init (assumes snippets are already uploaded)
qm set $VM_ID --cicustom "user=local:snippets/debug-probe-hub-user.yml,network=local:snippets/debug-probe-hub-network.yml"

echo "VM created. Add USB devices with:"
echo "  lsusb  # to find device IDs"
echo "  qm set $VM_ID --usb0 host=VENDOR:PRODUCT"
echo ""
echo "Then start with: qm start $VM_ID"
SETUP_SCRIPT
)
```

## Step-by-Step (Minimal)

### 1. Prepare and Upload Cloud-init Files

```bash
# On your local machine
cd deploy
cp cloud-init-user-data.template.yml cloud-init-user-data.yml
cp cloud-init-network.template.yml cloud-init-network.yml

# Edit and replace TODO placeholders
nano cloud-init-user-data.yml  # Fix: YOUR_USERNAME_HERE, YOUR_SSH_PUBLIC_KEY_HERE, YOUR_GITHUB_USERNAME
nano cloud-init-network.yml    # Fix: IP, gateway, DNS

# Upload to Proxmox
scp cloud-init-user-data.yml root@proxmox:/var/lib/vz/snippets/debug-probe-hub-user.yml
scp cloud-init-network.yml root@proxmox:/var/lib/vz/snippets/debug-probe-hub-network.yml
```

### 2. Create VM on Proxmox

```bash
# SSH into Proxmox host
ssh root@proxmox

# Download Ubuntu image (once)
cd /var/lib/vz/template/iso
wget https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img

# Create VM
VM_ID=100
qm create $VM_ID --name debug-probe-hub --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk $VM_ID ubuntu-24.04-server-cloudimg-amd64.img local-lvm
qm set $VM_ID --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-$VM_ID-disk-0 --boot c --bootdisk scsi0
qm set $VM_ID --ide2 local-lvm:cloudinit
qm set $VM_ID --cicustom "user=local:snippets/debug-probe-hub-user.yml,network=local:snippets/debug-probe-hub-network.yml"
```

### 3. Add USB Devices

```bash
# Find USB devices
lsusb

# Example output:
# Bus 001 Device 005: ID 1366:0105 SEGGER J-Link
# Bus 001 Device 006: ID 1a86:8010 QinHeng Electronics WCH-Link

# Add devices by VID:PID
qm set $VM_ID --usb0 host=1366:0105  # J-Link
qm set $VM_ID --usb1 host=1a86:8010  # WCH-Link
```

### 4. Start VM

```bash
qm start $VM_ID

# Monitor console (optional)
qm terminal $VM_ID
```

### 5. Verify (after 3-5 minutes)

```bash
# SSH into VM (use YOUR username from cloud-init config)
ssh kazcomy@192.168.1.234

# Check services
systemctl status debug-probe-hub
docker ps
curl http://localhost:8080/status
```

## Common Issues

### Cloud-init not running

```bash
# On VM
cloud-init status
cat /var/log/cloud-init-output.log
```

### Wrong username

Make sure you replaced ALL occurrences of `kazcomy` in `cloud-init-user-data.yml`:
- `users:` section
- `usermod` command
- `chown` command
- `sudo -u` command
- `sed` command

### Network not configured

Check interface name matches in `cloud-init-network.yml`:
```bash
ip a  # on VM to see actual interface name (ens18, eth0, etc.)
```

### USB devices not visible

```bash
# On VM
lsusb
ls -l /dev/probes/

# Reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Access Your Hub

After successful deployment:
- **Web API**: http://192.168.1.234:8080
- **SSH**: ssh kazcomy@192.168.1.234

Test the API:
```bash
curl http://192.168.1.234:8080/status
curl http://192.168.1.234:8080/probes
curl "http://192.168.1.234:8080/probes/search?interface=jlink"
```

## Need More Help?

See the full [README.md](README.md) for detailed explanations and troubleshooting.
