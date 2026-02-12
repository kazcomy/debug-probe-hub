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

```bash
curl http://<debug-hub-host>:8080/targets
```

### `POST /dispatch`

Flash firmware or start debug/print mode.

- Required form fields: `target`, `probe`, `mode`
- `mode`: `flash`, `debug`, or `print`
- For `flash`, attach firmware as `file=@...`
- If the same `probe` already has an active `debug`/`print` session, dispatch returns busy until that session exits.

Flash:

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=1" \
  -F "mode=flash" \
  -F "file=@firmware.hex"
```

Debug:

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=nrf52840" \
  -F "probe=1" \
  -F "mode=debug"
```

Print (if target/interface supports it):

```bash
curl -X POST http://<debug-hub-host>:8080/dispatch \
  -F "target=ch32v203" \
  -F "probe=4" \
  -F "mode=print"
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
