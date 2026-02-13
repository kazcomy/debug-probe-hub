# Architecture
## Multi-Container and Multi-Probe Runtime

```mermaid
flowchart TB
    subgraph Clients["Remote Clients"]
        R1[Dev Container A]
        R2[Dev Container B]
        R3[Dev Container C]
    end

    subgraph HubVM["Debug Probe Hub VM"]
        API[server.py\n/status /probes/search /dispatch]
        DISP[debug_dispatcher.py\nrouting + lock + docker exec]

        subgraph CSet["Per-(Toolchain, Probe) Containers (same images, separate instances)"]
            Cjlink1[debug-box-jlink-p1]
            Ccmsis3[debug-box-cmsisdap-p3]
            Cesp1[debug-box-esp-p1]
            Cwch4[debug-box-wch-p4]
        end

        subgraph Locks["Probe Locks"]
            L1[/probe_1.lock/]
            L2[/probe_2.lock/]
            L3[/probe_3.lock/]
            L4[/probe_4.lock/]
        end
    end

    subgraph USB["Passed-through USB devices"]
        P1[J-Link #1]
        P2[J-Link #2]
        P3[CMSIS-DAP #1]
        P4[WCH-Link #1]
        P5[WCH-Link #2]
    end

    R1 --> API
    R2 --> API
    R3 --> API
    API --> DISP
    DISP --> L1
    DISP --> L2
    DISP --> L3
    DISP --> L4
    DISP --> Cjlink1
    DISP --> Ccmsis3
    DISP --> Cesp1
    DISP --> Cwch4

    Cjlink1 -. "/dev" .-> P1
    Ccmsis3 -. "/dev" .-> P3
    Cesp1 -. "/dev" .-> P1
    Cwch4 -. "/dev" .-> P4
```

## Why per-(toolchain, probe) containers

This project uses per-(toolchain, probe) containers to avoid tool concurrency issues:

- Still one image per toolchain, but multiple containers (one per compatible `(toolchain, probe_id)` pair).
- Prevents "cleanup kills other sessions" and helps with commercial tools that can't run concurrently in a shared environment.
- Locking remains probe-specific (`/var/lock/probe_{id}.lock`).
- For `debug` and `print`, a background lock monitor keeps the probe lock while session process is alive, preventing accidental same-probe replacement.
- Containers are started lazily at dispatch time (`docker-compose up -d <container>`), so idle probes do not require pre-starting every container.

## Architecture decisions

### Decision A: One probe = one container + one dedicated IP (rejected)

Question:
- "Why not assign each probe to a separate container with its own IP, and let clients switch by IP?"

Reasons it was rejected:
- Client burden becomes high: each project/tool profile must manage endpoint/IP switching logic.
- Operational burden grows with probe count: IP management, service discovery, and per-endpoint health checks increase.
- Isolation benefit is limited in this system: containers use `privileged: true` and `/dev:/dev`, so USB visibility is shared at device-node level.
- Concurrency/control problems are already handled by probe-level routing + lock files, without forcing clients to manage many endpoints.

### Decision B: One probe = one Mini PC/Raspberry Pi + one IP (rejected)

Question:
- "Why not physically split probes across multiple Mini PCs/Raspberry Pis and switch by host IP?"

Reasons it was rejected:
- Hardware and maintenance cost scale linearly (hosts, power, storage, OS updates, monitoring).
- Failure surface increases: more nodes mean more network and lifecycle drift issues.
- Capacity becomes fragmented (idle probes on one host cannot be flexibly reused as easily).
- For this use case, centralizing probes in one Hub VM with per-(toolchain, probe) container instances gives enough operational separation at much lower cost.

## Mapping rules

- Target selects container via `targets.<target>.container` in `config.yml` (string or per-interface map).
- Probe compatibility is checked by `targets.<target>.compatible_probes`.
- Actual command is selected by `targets.<target>.commands.<interface>.<mode>`.
- Generated compose services are limited to compatible mappings derived from target container + compatible interfaces.

## Source references

- Container runtime and USB mount: `generate_docker_compose_probes.py` (generates `docker-compose.probes.yml`)
- Locking and dispatch flow: `debug_dispatcher.py`
- Configuration schema and target/container resolution: `config_loader.py`, `config.yml`
