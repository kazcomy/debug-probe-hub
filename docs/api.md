# API Reference

Base URL: `http://<debug-hub-host>:8080`

## Endpoints

### `GET /status`

Check probe connection status.

```bash
curl http://<debug-hub-host>:8080/status
```

### `GET /probes`

List configured probes.

```bash
curl http://<debug-hub-host>:8080/probes
```

### `GET /probes/search`

Search probes by interface, VID/PID, serial, or name.

Query params:
- `interface`
- `vid` or `vendor_id`
- `pid` or `product_id`
- `serial`
- `name`

Examples:

```bash
curl "http://<debug-hub-host>:8080/probes/search?interface=jlink"
curl "http://<debug-hub-host>:8080/probes/search?vid=1366&pid=0105"
curl "http://<debug-hub-host>:8080/probes/search?interface=cmsis-dap&serial=C2428F064718"
```

### `GET /targets`

List supported targets.
Each target includes compatible probe interfaces and transport policy (`default`/`allowed`) per interface.

```bash
curl http://<debug-hub-host>:8080/targets
```

### `POST /dispatch`

Flash firmware or start debug/print mode.

- Required form fields: `target`, `probe`, `mode`
- `mode`: `flash`, `debug`, or `print`
- Optional form field: `transport` (for example: `swd`, `jtag`)
- If `transport` is provided, it must be allowed by `targets.<target>.transports.<interface>.allowed`.
- For `flash`, attach firmware as `file=@...`
- If the same `probe` already has an active `debug`/`print` session, dispatch returns busy until that session exits.

Flash:

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=stm32g4" \
  -F "probe=1" \
  -F "transport=swd" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

Debug:

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=stm32g4" \
  -F "probe=1" \
  -F "transport=jtag" \
  -F "mode=debug"
```

When `mode=debug` succeeds, connect your GDB client directly to:

- `<debug-hub-host>:(ports.gdb_base + probe_id)`
- Example: `gdb_base=3330`, `probe=1` -> `3331`

Print (if target/interface supports it):

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=ch32v203" \
  -F "probe=4" \
  -F "mode=print"
```

### `POST /session/stop`

Force-stop active session processes for a probe and wait for lock release.

- Required form fields: `probe`
- Optional form field: `kind` (`debug`, `print`, `all`; default: `all`)
- Response includes `status` and `log`

Example:

```bash
curl -X POST http://<debug-hub-host>:8080/session/stop \
  -d "probe=1" \
  -d "kind=all"
```

## Common usage patterns

### Probe discovery then dispatch

```bash
PROBE_ID=$(curl -s "http://<debug-hub-host>:8080/probes/search?interface=jlink" | jq -r '.matches[0].id')
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=$PROBE_ID" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

### Select specific probe by serial

```bash
PROBE_ID=$(curl -s "http://<debug-hub-host>:8080/probes/search?interface=wch-link&serial=50CE8F06D5AF" | jq -r '.matches[0].id')
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=ch32v003" \
  -F "probe=$PROBE_ID" \
  -F "mode=debug"
```

## Debug quick start (LAN direct)

1. Start debug session via `/dispatch` with `mode=debug`.
2. Compute GDB endpoint as `<debug-hub-host>:(gdb_base + probe_id)`.
3. Connect from your GDB client:

```gdb
target remote <debug-hub-host>:<gdb_port>
monitor reset halt
```

Example (`gdb_base=3330`, `probe=1`):

```gdb
target remote remoteprogrammer.local.lan:3331
```

## Debug session lifecycle

- `mode=debug` starts a server process and holds probe lock.
- First GDB client must attach within 60 seconds or session is auto-stopped.
- Once attached, session is auto-stopped immediately when all GDB clients disconnect.
- Reconnect after disconnect requires a new `/dispatch` request.
- Manual recovery is available via `POST /session/stop`.

## Debug troubleshooting

- Probe busy means another active `debug`/`print` session is holding the probe lock.
- Run `POST /session/stop` for the probe before resorting to service restart.
- Target/transport mismatch can be checked via `GET /targets` (`allowed` transport list).
- Server process check: `systemctl status debug-probe-hub`
- Server logs: `journalctl -u debug-probe-hub -n 100`
- Port reachability from client: `nc -vz <debug-hub-host> <gdb_port>`
- Note: `/var/lock/probe_<id>.lock` file may remain on disk; lock state is determined by `flock`, not file existence.
