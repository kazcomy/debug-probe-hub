# Operations Guide

## Production deployment

Use `docs/deploy.md` for Proxmox + cloud-init provisioning and first boot workflow.

## Manual/local setup

```bash
git clone https://github.com/yourusername/debug-probe-hub.git /opt/debug-probe-hub
cd /opt/debug-probe-hub
./setup.sh
```

## Start services (systemd)

```bash
sudo systemctl enable debug-probe-hub.service
sudo systemctl start debug-probe-hub.service

systemctl status debug-probe-hub-pre-setup.service
systemctl status debug-probe-hub-setup.service
systemctl status debug-probe-hub.service
```

Service sequence:
1. `debug-probe-hub-pre-setup.service`
2. `debug-probe-hub-setup.service`
3. `debug-probe-hub.service`

## Manual start (without systemd)

```bash
python3 generate_docker_compose_probes.py --output docker-compose.probes.yml
docker-compose -f docker-compose.probes.yml up -d
python3 server.py
```

## WCH toolchain requirement

WCH image needs private toolchain access. Configure `docker-compose.override.yml` using `docker-compose.override.yml.template`; the generator merges those build args into `docker-compose.probes.yml`.

## Troubleshooting

### Probes not detected

```bash
ls -l /dev/probes/
sudo udevadm info /dev/probes/probe_1
```

### Cloud-init login issue (Proxmox image)

```bash
cloud-init status
sudo tail -n 200 /var/log/cloud-init-output.log
```

Verify `ssh_pwauth` and `chpasswd` settings in cloud-init user-data.

### Container issues

```bash
docker ps
docker-compose logs debug-box-std
docker-compose logs debug-box-esp
docker-compose logs debug-box-wch
```

### Port conflicts

Adjust `ports.gdb_base`, `ports.telnet_base`, `ports.rtt_base` in `config.yml`.

### Permission issues

```bash
sudo usermod -a -G dialout "$USER"
```

Re-login after changing group membership.

## Development checks

```bash
python3 probe_status.py
python3 -c "from config_loader import get_config; print(get_config().get_all_probes())"
python3 debug_dispatcher.py nrf52840 1 debug
```
