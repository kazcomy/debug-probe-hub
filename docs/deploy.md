# Proxmox + Cloud-init Deployment

This document is only for provisioning Debug Probe Hub on Proxmox using cloud-init.
If you are not using Proxmox/cloud-init, use `docs/operations.md`.

## 1. Prepare cloud-init files

```bash
cd deploy
cp cloud-init-user-data.template.yml cloud-init-user-data.yml
cp cloud-init-network.template.yml cloud-init-network.yml
```

Edit both files and replace all placeholders.

Sanity check:

```bash
grep -nE 'YOUR_|TODO' cloud-init-user-data.yml cloud-init-network.yml || true
```

## 2. Create VM on Proxmox

Run on Proxmox host:

```bash
VM_ID=100
VM_NAME="debug-probe-hub"
STORAGE="local-lvm"
CLOUD_IMAGE="/var/lib/vz/template/iso/ubuntu-24.04-server-cloudimg-amd64.img"

qm create $VM_ID --name $VM_NAME --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk $VM_ID $CLOUD_IMAGE $STORAGE
qm set $VM_ID --scsihw virtio-scsi-pci --scsi0 $STORAGE:vm-$VM_ID-disk-0
qm resize $VM_ID scsi0 100G
qm set $VM_ID --boot c --bootdisk scsi0
qm set $VM_ID --ide2 $STORAGE:cloudinit
qm set $VM_ID --cicustom "user=local:snippets/cloud-init-user-data.yml,network=local:snippets/cloud-init-network.yml"
qm cloudinit update $VM_ID
```

Add required USB passthrough devices (example):

```bash
qm set $VM_ID --usb0 host=1366:0105
qm set $VM_ID --usb1 host=1a86:8010
qm set $VM_ID --usb2 host=1a86:8010
```

Start VM:

```bash
qm start $VM_ID
```

## 3. First boot handoff (inside VM)

After cloud-init is done:

```bash
ssh YOUR_USERNAME@<debug-hub-ip>
cloud-init status
```

Expected: `status: done`

Configure WCH private toolchain access:

```bash
cd /opt/debug-probe-hub
cp docker-compose.override.yml.template docker-compose.override.yml
nano docker-compose.override.yml
```

Build/start:

```bash
sudo systemctl start debug-probe-hub-setup
sudo systemctl start debug-probe-hub
```

Verify:

```bash
systemctl status debug-probe-hub
docker ps
curl http://localhost:8080/status
```

## 4. Re-deploy after config changes

If you change `config.yml` after initial deployment, re-running only `debug-probe-hub` is not enough.
You must re-run part of the manual operational flow so generated files and services are updated.

```bash
cd /opt/debug-probe-hub

# 1) Edit config
nano config.yml

# 2) Regenerate compose from config
python3 generate_docker_compose_probes.py --output docker-compose.probes.yml

# 3) Re-run setup/build phase (same as manual operation)
sudo systemctl restart debug-probe-hub-setup.service

# 4) Restart runtime service
sudo systemctl restart debug-probe-hub.service
```

If you changed probe mappings or udev-related settings, also re-run pre-setup:

```bash
sudo systemctl restart debug-probe-hub-pre-setup.service
```

## 5. Scope notes

- This guide does not cover API usage, architecture, or config extension.
- See:
  - `docs/api.md`
  - `docs/architecture.md`
  - `docs/configuration.md`
  - `docs/operations.md`

## 6. Troubleshooting (Proxmox-specific only)

Cloud-init login issue:

```bash
cloud-init status
sudo tail -n 200 /var/log/cloud-init-output.log
```

USB passthrough issue:

```bash
lsusb
ls -l /dev/probes/
```
