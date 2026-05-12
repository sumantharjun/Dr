# Smart Baby Feeding — Device Firmware Integration Contract

**Version:** 1.0  
**Base URL (production):** `https://<your-domain>`  
**Base URL (local dev):** `http://localhost:8000`

---

## Authentication

Every device request must include the device's API key. There are two forms depending on the transport:

| Transport | How to send the key |
|-----------|---------------------|
| HTTP (REST) | `X-Device-Api-Key: <api_key>` request header |
| WebSocket | `?api_key=<api_key>` query parameter in the connection URL |

The API key is provisioned when the device is registered via the mobile app (`POST /devices/`). It can be rotated by the user at any time (`POST /devices/{id}/rotate-key`); the new key must be flashed to the firmware before the old one expires.

---

## 1. WebSocket Connection

### Connect

```
ws://<host>/devices/ws/{device_id}?api_key=<api_key>
```

The server marks the device `online` and begins accepting events.  
The server sends a `ping` frame every **5 minutes** of silence — the device must reply with any valid message (e.g., a `status` event) or the connection will be closed.

### Connection close codes

| Code | Meaning |
|------|---------|
| 4001 | Missing or invalid credentials |
| 4003 | Device not found or API key mismatch |
| 1000 | Normal closure (server side) |

### Keep-alive strategy (firmware recommendation)

- If no data to send, reply to the server's `{"type":"ping"}` with `{"type":"status","payload":{}}`.
- Reconnect with **exponential back-off**: 1 s → 2 s → 4 s → 8 s → max 60 s.

---

## 2. Events: Device → Server (WebSocket)

All events are JSON objects with a `"type"` field. The server ignores unknown types.

### `wash_progress`
Report wash cycle status.

```json
{
  "type": "wash_progress",
  "cycle_id": 42,
  "status": "running",
  "progress_pct": 65
}
```

| Field | Type | Values |
|-------|------|--------|
| `cycle_id` | int | ID returned when the wash was started |
| `status` | string | `"pending"` `"running"` `"completed"` `"failed"` |
| `progress_pct` | int | 0 – 100 |

### `dispense_progress`
Report milk dispense status.

```json
{
  "type": "dispense_progress",
  "log_id": 17,
  "status": "dispensing",
  "progress_pct": 40
}
```

| Field | Type | Values |
|-------|------|--------|
| `log_id` | int | ID returned in the dispense command |
| `status` | string | `"pending"` `"dispensing"` `"completed"` `"failed"` |
| `progress_pct` | int | 0 – 100 |

### `weight_report`
Real-time weight sensor reading (optional, for live display only — does **not** create a feeding log).

```json
{
  "type": "weight_report",
  "payload": {
    "weight_g": 280.5
  }
}
```

### `alert`
Device-initiated alert (low water, heating error, etc.).

```json
{
  "type": "alert",
  "payload": {
    "severity": "warning",
    "message": "Water reservoir below 20%"
  }
}
```

| `severity` | Use for |
|------------|---------|
| `info` | Informational events |
| `warning` | Degraded but operational |
| `error` | Feature unavailable |
| `critical` | Requires immediate attention |

### `status`
Heartbeat / general device status.

```json
{
  "type": "status",
  "payload": {
    "firmware_version": "1.2.3",
    "water_level_pct": 80,
    "temperature_c": 37.2
  }
}
```

### `metric`
Energy / water consumption metrics.

```json
{
  "type": "metric",
  "payload": {
    "power_kwh": 0.12,
    "water_liters": 1.5
  }
}
```

---

## 3. Commands: Server → Device (WebSocket)

The server pushes these JSON frames when the user triggers an action from the app.

### `start_wash`

```json
{
  "type": "command",
  "command": "start_wash",
  "mode": "full_cycle",
  "cycle_id": 42
}
```

Modes: `"full_cycle"` `"wash"` `"deep_clean"` `"dispense"`

After receiving this, the device should begin the wash and stream `wash_progress` events until `status` reaches `"completed"` or `"failed"`.

### `dispense`

```json
{
  "type": "command",
  "command": "dispense",
  "temperature_c": 37.0,
  "volume_ml": 150.0,
  "log_id": 17
}
```

After receiving this, stream `dispense_progress` events until done.

### `stop_wash` / `stop_dispense`

```json
{
  "type": "command",
  "command": "stop_wash"
}
```

Abort the current operation and send a final progress event with `status: "failed"`.

### `reboot`

```json
{ "type": "command", "command": "reboot" }
```

### `status` (request)

```json
{ "type": "command", "command": "status" }
```

Respond with a `status` event (see §2).

---

## 4. HTTP REST Endpoints (Device → Server)

Use HTTP for operations that need reliable delivery with a response confirmation.

### 4a. Report Wash Progress

```
POST /washing/progress
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{
  "cycle_id": 42,
  "status": "completed",
  "progress_pct": 100
}
```

Response `200 OK`:

```json
{
  "id": 42,
  "device_id": 7,
  "mode": "full_cycle",
  "status": "completed",
  "progress_pct": 100,
  "started_at": "2026-04-25T10:00:00",
  "completed_at": "2026-04-25T10:08:30"
}
```

The server also broadcasts a `wash_progress` WebSocket frame to all connected app clients for this device.

**Status values:** `pending` → `running` → `completed` | `failed`

---

### 4b. Report Dispense Progress

```
POST /dispensing/progress
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{
  "log_id": 17,
  "status": "completed",
  "progress_pct": 100
}
```

Response `200 OK`:

```json
{
  "id": 17,
  "device_id": 7,
  "temperature_c": 37.0,
  "volume_ml": 150.0,
  "status": "completed",
  "progress_pct": 100,
  "created_at": "2026-04-25T10:05:00",
  "completed_at": "2026-04-25T10:05:45"
}
```

The server also broadcasts a `dispense_progress` WebSocket frame to all connected app clients.

**Status values:** `pending` → `dispensing` → `completed` | `failed`

---

### 4c. Report Feeding (Weight Sensor)

Call this **once per feeding session**, after the baby finishes feeding, when the device has stable before/after weight readings.

```
POST /feeding/device-report
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{
  "weight_before_g": 320.0,
  "weight_after_g": 190.0,
  "feed_time": "2026-04-25T09:30:00"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `weight_before_g` | Yes | Bottle weight before feeding (grams) |
| `weight_after_g` | Yes | Bottle weight after feeding (grams) |
| `feed_time` | No | ISO-8601 datetime; defaults to server time if omitted |

Response `201 Created`:

```json
{
  "id": 88,
  "user_id": 3,
  "device_id": 7,
  "feed_time": "2026-04-25T09:30:00",
  "weight_before_g": 320.0,
  "weight_after_g": 190.0,
  "milk_consumed_ml": 126.1,
  "method": "device",
  "notes": null,
  "created_at": "2026-04-25T09:30:05"
}
```

`milk_consumed_ml` is calculated server-side: `(weight_before_g - weight_after_g) × 0.97`

Constraints:
- `weight_before_g` must be ≥ `weight_after_g`
- Both values must be non-negative

---

## 5. Error Responses

All HTTP errors follow the standard FastAPI format:

```json
{ "detail": "human-readable message" }
```

| HTTP Status | Cause |
|-------------|-------|
| 400 | Validation failed (bad values, wrong status) |
| 403 | Missing or invalid `X-Device-Api-Key` |
| 404 | `cycle_id` / `log_id` not found or belongs to a different device |
| 429 | Rate limit exceeded (auth endpoints only) |
| 500 | Server error — retry with back-off |

---

## 6. Retry Guidelines

| Scenario | Recommended action |
|----------|--------------------|
| HTTP 5xx | Exponential back-off: 1 s, 2 s, 4 s, max 3 retries |
| HTTP 403 | Do not retry — API key is invalid; alert user via app |
| HTTP 404 | Do not retry — `log_id`/`cycle_id` is wrong |
| WebSocket disconnect | Reconnect with back-off (see §1) |
| No network | Queue events locally, flush when reconnected |

---

## 7. Typical Device Flow

### Wash cycle

```
Device                          Server
  │  ── WS: connect ──────────►  │  (device online)
  │  ◄── WS: command start_wash──│  (app user pressed "Start Wash")
  │  ── HTTP POST /washing/progress {status:"running", pct:10} ──► │
  │  ── HTTP POST /washing/progress {status:"running", pct:50} ──► │
  │  ── HTTP POST /washing/progress {status:"completed", pct:100}─► │  (app sees live update)
```

### Feeding session

```
[Parent places bottle on scale before feeding]
[Baby feeds]
[Parent places bottle on scale after feeding]
Device ── HTTP POST /feeding/device-report {before:320, after:190} ──► Server
Server creates FeedingLog, runs feeding analysis, may trigger alert ──► App
```

### Dispense

```
App user sets temp + volume ──► Server ──► WS command "dispense" ──► Device
Device starts pumping:
  Device ── HTTP POST /dispensing/progress {status:"dispensing", pct:50} ──► Server ──► App
  Device ── HTTP POST /dispensing/progress {status:"completed", pct:100} ──► Server ──► App
```

---

## 8. QR Pairing

During first-time pairing, the mobile app camera scans a QR code printed on the device.

Expected QR content format:

```
SBFD:MAC=AA:BB:CC:DD:EE:FF
```

Where `AA:BB:CC:DD:EE:FF` is the device MAC address. The app uses this to pre-fill the pairing form and calls `POST /devices/` to register the device and receive the API key. Flash the returned `api_key` to the device firmware.

---

## 9. Changelog

| Date | Change |
|------|--------|
| 2026-04-25 | Initial version — WebSocket + 3 HTTP device endpoints |
