# Debug Probe Hub

Unified remote debugging and firmware flashing hub for multiple MCU targets and probe types.

## Start Here

- Proxmox production deployment: `docs/deploy.md`
- Architecture and diagrams: `docs/architecture.md`
- API reference and request examples: `docs/api.md`
- Configuration guide (`config.yml`): `docs/configuration.md`
- Operations (manual setup, runbook, troubleshooting): `docs/operations.md`

## System Topology

```mermaid
C4Component
    title Debug Probe Infrastructure Component Diagram

    Deployment_Node(win, "Local Workstation", "Windows 11") {
        Component(vscode, "VSCode", "IDE", "Remote Development Interface")
    }

    Deployment_Node(proxmox_dev, "Development PC (Proxmox)", "Server") {
        Container(dns, "Local DNS VM", "bind9/Unbound", "localdns.local.lan")
        Container(devsrv, "Dev Container Host VM", "Docker/Podman", "devsrv.local.lan")
    }

    Deployment_Node(proxmox_probe, "Mini PC near target (Proxmox)", "Edge Device") {
        Container_Boundary(hub_vm, "Debug Probe Hub VM") {
            Component(api, "Hub API Server", "REST/HTTP", "/dispatch endpoint")
            
            Boundary(containers, "Debug Box Containers") {
                Component(cstd1, "debug-box-std-p1", "Container", "J-Link logic")
                Component(cstd3, "debug-box-std-p3", "Container", "CMSIS-DAP logic")
                Component(cwch2, "debug-box-wch-p2", "Container", "WCH-Link logic")
                Component(cwch4, "debug-box-wch-p4", "Container", "WCH-Link logic")
            }
        }
    }

    Deployment_Node(hardware, "Physical Hardware", "Probes") {
        ComponentDb(j1, "J-Link #1", "USB")
        ComponentDb(d1, "CMSIS-DAP #1", "USB")
        ComponentDb(w1, "WCH-Link #1", "USB")
        ComponentDb(w2, "WCH-Link #2", "USB")
    }

    Rel(vscode, devsrv, "SSH / Remote Dev", "TCP/22")
    Rel(devsrv, api, "HTTP Request", "JSON/REST")
    
    Rel(api, cstd1, "Internal Routing")
    Rel(api, cstd3, "Internal Routing")
    Rel(api, cwch2, "Internal Routing")
    Rel(api, cwch4, "Internal Routing")

    Rel(cstd1, j1, "USB Passthrough")
    Rel(cstd3, d1, "USB Passthrough")
    Rel(cwch2, w1, "USB Passthrough")
    Rel(cwch4, w2, "USB Passthrough")
    
    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

## USB and Container Model

- One image per toolchain, one container per `probe_id` (example: `debug-box-std-p1`).
- Probe routing is done by `probe_id` + `serial` and each probe gets its own container instance.
- Probe-level lock files (`/var/lock/probe_{id}.lock`) serialize same-probe access while allowing parallel access to different probes.
- Containers mount `/dev:/dev` with `privileged: true`, so any USB device passed from Proxmox into the Hub VM is visible to containers.

## Repository Placement

- Install this repository on the Debug Probe Hub Ubuntu VM (`/opt/debug-probe-hub`).
- Do not install this repository on Windows client or `devsrv` when those are separate roles.
- In cloud-init deployment, clone can be done automatically (see `deploy/cloud-init-user-data.template.yml`).

## Documentation Layout

- `docs/deploy.md`: Proxmox + cloud-init provisioning runbook
- `docs/architecture.md`: architecture and concurrency behavior
- `docs/api.md`: endpoint contract and usage patterns
- `docs/configuration.md`: adding probes/targets/interfaces
- `docs/operations.md`: local/manual setup, systemd flow, troubleshooting

## Quick Validation

```bash
curl http://<debug-hub-host>:8080/status
curl "http://<debug-hub-host>:8080/probes/search?interface=jlink"
```

## License

MIT. See `LICENSE`.
