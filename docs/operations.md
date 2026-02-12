# Operations (Non-Proxmox / Manual)

This document is for manual operation without Proxmox/cloud-init.
If you use Proxmox + cloud-init, use `docs/deploy.md`.

## Manual install policy

- This project does not ship a universal installer for every environment.
- For manual installs, use Ubuntu (or compatible Linux), read `setup.sh`, and install required software for your environment.
- At minimum you need working: `docker`, `docker-compose`, `python3`, `pip3`, and permissions for Docker/udev operations.

## Manual setup

```bash
git clone https://github.com/yourusername/debug-probe-hub.git /opt/debug-probe-hub
cd /opt/debug-probe-hub
./setup.sh
```

What `setup.sh` handles:

- installs Python package `pyyaml`
- generates and installs udev rules
- generates `docker-compose.probes.yml`
- builds Docker images

## Start and stop

Systemd:

```bash
sudo systemctl enable debug-probe-hub.service
sudo systemctl start debug-probe-hub.service
sudo systemctl stop debug-probe-hub.service
```

Manual:

```bash
python3 generate_docker_compose_probes.py --output docker-compose.probes.yml
docker-compose -f docker-compose.probes.yml up -d
python3 server.py
```

## Update

```bash
cd /opt/debug-probe-hub
git pull
python3 generate_docker_compose_probes.py --output docker-compose.probes.yml
sudo systemctl restart debug-probe-hub-setup.service
sudo systemctl restart debug-probe-hub.service
```

## Troubleshooting (generic)

Service/logs:

```bash
systemctl status debug-probe-hub
journalctl -u debug-probe-hub -n 100
```

Container/runtime:

```bash
docker ps
docker-compose -f docker-compose.probes.yml logs
```

Probe visibility:

```bash
ls -l /dev/probes/
curl http://localhost:8080/status
```

Port conflicts:

- Adjust `ports.gdb_base`, `ports.telnet_base`, `ports.rtt_base` in `config.yml`.
