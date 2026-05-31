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

### How WS events are processed

Events split into two groups by behaviour:

| Event type | Persists to DB? | Notes |
|------------|-----------------|-------|
| `wash_progress` | ✅ Yes | Equivalent to `POST /washing/progress`. |
| `dispense_progress` | ✅ Yes | Equivalent to `POST /dispensing/progress`. |
| `alert` | ✅ Yes | Equivalent to `POST /alerts/`. `alert_type` is **required**. |
| `metric` | ✅ Yes | Equivalent to `POST /metrics/`. |
| `weight_report` | ❌ No (ephemeral, live display only) | |
| `status` | ❌ No (only updates `last_seen`) | |

**You no longer see your own events echoed back** — the originating socket is
excluded from the broadcast (since 2026-05-28). If you need a confirmation,
look at the response shape on the equivalent HTTP route, or call
`GET /washing/history` / `GET /dispensing/history` to verify.

If a persistable event fails validation (bad `cycle_id`, missing
`alert_type`, out-of-range `progress_pct`, etc.), the server **does not
broadcast** the bad data to app clients. Instead it sends an `error` frame
back **only to the sender**:

```json
{
  "type": "error",
  "for": "wash_progress",
  "status_code": 404,
  "detail": "Cycle not found",
  "original": { "type": "wash_progress", "cycle_id": 9999, ... }
}
```

The connection stays open after an error frame — fix the payload and resend.

### `wash_progress`
Report wash cycle status. Persists; mirrors `POST /washing/progress`.

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
Report milk dispense status. Persists; mirrors `POST /dispensing/progress`.

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
Device-initiated safety alert. **Persists** to the alerts table; mirrors
`POST /alerts/` (see §4e for the closed catalog of `alert_type` values).

```json
{
  "type": "alert",
  "alert_type": "low_detergent",
  "message": "Water reservoir below 20%",
  "severity": "warning"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `alert_type` | Yes | One of `overheating` `malfunction` `washing_error` `low_detergent` (see §4e). |
| `message` | Yes | 1–500 chars, free text. |
| `severity` | No | If omitted, server uses the catalog default for the `alert_type`. |

Fields nested under `"payload": {...}` are also accepted for backward
compatibility with the original WS shape, but prefer flat fields.

### `status`
Heartbeat / general device status. Ephemeral — only `last_seen` is updated.

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
Energy / water consumption metric. **Persists**; mirrors `POST /metrics/`.

```json
{
  "type": "metric",
  "power_kwh": 0.62,
  "water_liters": 2.8,
  "cycle_id": 42
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `power_kwh` | Yes | ≥ 0, kilowatt-hours consumed this cycle. |
| `water_liters` | Yes | ≥ 0, liters consumed this cycle. |
| `cycle_id` | No (recommended) | Wash cycle this metric belongs to. |

Fields nested under `"payload": {...}` are also accepted for backward
compatibility, but prefer flat fields.

---

## 3. Commands: Server → Device

When the app user triggers an action (e.g. "Start Wash"), the server emits a
JSON command frame addressed to the device. There are **two transports** — the
firmware can use **either**, never both:

| Transport | How to receive | Best for |
|-----------|----------------|----------|
| WebSocket | Connect to `/devices/ws/{device_id}?api_key=...` and read frames as they arrive | Low-latency, push-based; preferred when firmware can hold a long-lived socket |
| HTTP polling | Periodically `GET /devices/commands/pending` with `X-Device-Api-Key` | Simpler firmware; fine when sub-second latency isn't required |

The frame shape is identical on both transports — see the per-command sections
below. Polling is described in §4d.

#### Why commands carry `cycle_id` / `log_id`

Each `start_wash` command includes a `cycle_id`, and each `dispense` command
includes a `log_id`. The firmware should **store the ID locally when the
command is received and echo it back in every subsequent progress update**
(see §4a, §4b) until the operation reaches `completed` or `failed`.

Even though only one cycle or dispense will ever be active at a time, the
ID is required for three reasons:

1. **History.** `washing_cycles` and `milk_dispense_logs` accumulate rows
   indefinitely. The server needs the ID to know which historical row to
   update — it does **not** infer it from "the latest running cycle."
2. **Idempotent retries.** If the network drops a progress packet and the
   firmware retries, the explicit ID guarantees both attempts target the
   same row, so re-delivery is safe.
3. **Crash recovery.** If a previous cycle ever gets stuck in `running`
   (device reboot mid-cycle, network outage, etc.), inferring "the latest
   in-flight cycle" becomes ambiguous. Explicit IDs make recovery clean.

The firmware cost is essentially one `int` per active operation. The
server-side benefit is end-to-end determinism. Please don't try to omit
these in progress packets — the server will return `404 "Cycle not found"`
or `"Dispense log not found"`.

### 3a. Commands: Server → Device (WebSocket)

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

### 4d. Poll for Pending Commands (HTTP alternative to WebSocket)

```
GET /devices/commands/pending
Header: X-Device-Api-Key: <api_key>
```

Response `200 OK` — array of pending commands, oldest first. Each command is
returned **once**: the server marks it as fetched on read.

```json
[
  {
    "id": 7,
    "command": "start_wash",
    "payload": {
      "type": "command",
      "command": "start_wash",
      "mode": "full_cycle",
      "cycle_id": 42
    },
    "created_at": "2026-05-24T10:00:05"
  },
  {
    "id": 8,
    "command": "dispense",
    "payload": {
      "type": "command",
      "command": "dispense",
      "temperature_c": 37.0,
      "volume_ml": 150.0,
      "log_id": 17
    },
    "created_at": "2026-05-24T10:00:11"
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Row ID (for diagnostics/logging only) |
| `command` | string | Convenience copy of `payload.command` |
| `payload` | object | Full command frame — same shape as the WebSocket frame in §3a |
| `created_at` | ISO datetime | When the user issued the command on the app |

Side effect: polling marks the device `online` and updates `last_seen`, so the
app's "Devices" page shows liveness without a WebSocket connection.

**Recommended poll interval:**
- 5 s when idle
- 1–2 s while the user is expected to act (e.g. while showing a "Ready" screen)
- Slow back down once a wash/dispense is running — the device already streams
  progress via §4a / §4b, so the server doesn't push more commands until the
  current operation finishes

**Important:** Each command is delivered exactly once. If the device crashes
between fetching and executing, the command is lost — the user would have to
retry from the app. For most baby-feeder flows this is acceptable; for safety-
critical actions, the app already shows the result via the progress endpoints.

---

### 4e. Push a Safety Alert

```
POST /alerts/
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Use this when the device detects a condition the parent must know about
(overheating, hardware fault, etc.). The alert appears on the user's
Alerts page in real time and triggers a push notification on the app.

Request body:

```json
{
  "device_id": 7,
  "alert_type": "overheating",
  "message": "Heater overshoot — water reached 62 °C",
  "severity": "critical"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `device_id` | Yes | Must match the device the API key belongs to. |
| `alert_type` | Yes | One of the four safety types below — closed set. |
| `message` | Yes | 1–500 char human-readable description. |
| `severity` | No | If omitted, the server fills in the catalog default for this alert_type. |

**Valid `alert_type` values (MOU Annexure A1 safety alerts):**

| `alert_type` | When to send | Default severity |
|--------------|--------------|------------------|
| `overheating` | Milk or device temperature exceeded the safe limit. | `critical` |
| `malfunction` | Hardware or sensor failure — feature unavailable. | `error` |
| `washing_error` | Wash cycle aborted or detected an anomaly mid-cycle. | `error` |
| `low_detergent` | Detergent reservoir reading is below the low threshold. | `warning` |

> Server-generated alert types (`feeding_reminder`, `overdue_feed`,
> `low_intake`, `frequent_feeding`) are produced by the backend itself.
> The device must **not** send these; the API will reject them with `400`.

Response `201 Created`:

```json
{
  "id": 102,
  "device_id": 7,
  "alert_type": "overheating",
  "message": "Heater overshoot — water reached 62 °C",
  "severity": "critical",
  "is_read": false,
  "created_at": "2026-05-24T11:42:00"
}
```

Repeat alerts of the same type are intentionally **not** server-side
de-duplicated for safety alerts — every detection is recorded so the
parent has a full audit trail. The device firmware should rate-limit on
its end (e.g. don't re-fire `low_detergent` more than once per minute).

---

### 4f. Submit Metrics (per-cycle consumption)

After each wash cycle completes, the device reports how much **power**
and **water** it consumed. The server uses these to show the user their
cumulative energy / water savings versus a standard sterilizer baseline
(1.0 kWh + 5 L per cycle).

This is a **post-cycle one-shot** call — fire it once per completed wash,
*not* continuously during the cycle.

```
POST /metrics/
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{
  "device_id": 7,
  "cycle_id": 42,
  "power_kwh": 0.62,
  "water_liters": 2.8
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `device_id` | Yes | int | Must match the device the API key belongs to. |
| `cycle_id` | No | int | The wash cycle this metric belongs to. Optional, but **strongly recommended** — without it, the metric can't be linked to a specific cycle in the wash history. Same `cycle_id` you received in `start_wash`. |
| `power_kwh` | Yes | float ≥ 0 | Energy consumed during this cycle, in kilowatt-hours. |
| `water_liters` | Yes | float ≥ 0 | Water consumed during this cycle, in liters. |

Response `201 Created`:

```json
{
  "id": 88,
  "device_id": 7,
  "cycle_id": 42,
  "power_kwh": 0.62,
  "water_liters": 2.8,
  "recorded_at": "2026-05-24T19:38:17"
}
```

**Firmware flow:**

```
Device finishes wash cycle 42
   ↓ device measures total power + water consumed for that cycle
Device → HTTP POST /washing/progress {cycle_id:42, status:"completed", progress_pct:100}
Device → HTTP POST /metrics/ {device_id, cycle_id:42, power_kwh, water_liters}
   ↓
Server stores row → user sees updated savings on the dashboard
```

Send `/metrics/` **once per cycle**, after the `/washing/progress` packet
with `status:"completed"`. Don't stream interim values — only the final
totals.

**Important:** the metric POST is **not idempotent** — two POSTs for the
same cycle create two rows. Retry only on transport failures (5xx,
network), not on "I'm not sure if it got through" cases. When in doubt,
the device can `GET /metrics/history` to confirm before resending.

---

### 4g. Log Activity (audit / timeline events)

Use this to record human-readable timeline events the user will see on
the Activity page (cycle started, network reconnected, etc.). These are
audit-only — they don't affect any control flow.

```
POST /activity/
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{
  "device_id": 7,
  "event_type": "wash_completed",
  "description": "Full cycle finished in 8 min 30 sec"
}
```

**Allowed `event_type` values — closed set, please use these exact strings:**

| `event_type` | When to send |
|--------------|--------------|
| `device_online` | When the device boots up and successfully connects to the server. |
| `device_offline` | Just before a graceful shutdown / disconnect. Skip if the device is crashing — the server infers offline state from a lost WebSocket. |
| `network_reconnected` | After Wi-Fi drops and the device reconnects. |
| `wash_started` | When the device begins executing a wash cycle (after receiving `start_wash`, before the first progress packet). |
| `wash_completed` | When the wash cycle reaches 100 % successfully. |
| `wash_failed` | When the wash cycle is aborted or errors out mid-cycle. |
| `dispense_started` | When the device begins dispensing milk. |
| `dispense_completed` | When the requested volume has been dispensed successfully. |
| `dispense_failed` | When dispensing is aborted or errors out. |
| `alert_triggered` | Optional companion log when pushing a safety alert via `POST /alerts/`. Useful for the activity timeline. |
| `feeding_logged` | When the device reports a feeding via `POST /feeding/device-report`. |

Any other string is rejected with `422`. Please stick to the list above.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `device_id` | Yes | int | Must match the device the API key belongs to. |
| `event_type` | Yes | string | Must be one of the values in the table above. |
| `description` | No | string | Free-text, 0–500 chars, shown verbatim on the Activity timeline. Optional but recommended. |

**`description` examples** (omit if you don't have anything meaningful):

- `wash_completed` → `"Full cycle finished in 8 min 30 sec"`
- `wash_failed` → `"Aborted at 65 % — water inflow sensor timeout"`
- `network_reconnected` → `"Reconnected after a 12 s outage"`
- `alert_triggered` → `"Heater overshoot — water reached 62 °C"`
- `device_online` → `"Boot complete · firmware v1.2.3"`

Response `201 Created`:

```json
{
  "id": 88,
  "device_id": 7,
  "event_type": "wash_completed",
  "description": "Full cycle finished in 8 min 30 sec",
  "recorded_at": "2026-05-24T19:38:30"
}
```

**Usage tip:** treat these as fire-and-forget. 1–2 retries on 5xx is
plenty — don't burn battery / bandwidth retrying audit logs.

---

### 4h. Start a Wash from the Device (physical button)

Use this when the user starts a wash from the **physical controls on the
device itself**, not from the app. The server creates the cycle row,
returns a `cycle_id`, and notifies the user's app clients so the app's
progress bar lights up immediately.

```
POST /washing/device-start
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{ "mode": "full_cycle", "force": false }
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `mode` | Yes | string | One of `full_cycle`, `wash`, `deep_clean`, `dispense`. |
| `force` | No | bool | Default `false`. When `true`, any prior pending/running cycle on this device is force-failed (so this call can proceed). Use this for recovery after a crash, reboot, or dropped connection — see "Recovery from a stuck cycle" below. |

Response `201 Created`:

```json
{
  "id": 42,
  "device_id": 7,
  "mode": "full_cycle",
  "status": "pending",
  "progress_pct": 0,
  "initiated_by": "device",
  "started_at": "2026-05-24T19:38:00",
  "completed_at": null
}
```

The device **must** store `id` locally — that's the `cycle_id` it will
echo back in every subsequent `POST /washing/progress` call (see §4a),
exactly like a cycle started from the app.

**Concurrency rule:** the server allows only one active cycle per device
at a time. If a cycle already exists in `pending` or `running` state,
this endpoint returns `409 Conflict` with a body that includes details
about the active cycle so the firmware can choose between adopting it
and force-replacing it:

```json
{
  "detail": "A wash cycle is already active on this device. If it's stale, resend with `force: true`; if it just started (see active_cycle_started_at), adopt its `active_cycle_id` for subsequent progress packets.",
  "active_cycle_id": 42,
  "active_cycle_started_at": "2026-05-28T22:30:11",
  "active_cycle_initiated_by": "app",
  "active_cycle_status": "pending",
  "active_cycle_mode": "full_cycle"
}
```

#### Recommended firmware flow on 409

```
on POST /washing/device-start → 409:
   age = now - response.active_cycle_started_at
   if age < 15 seconds:
       # legitimate race — user tapped the app moments before pressing the
       # physical button. Adopt the cycle the server already has.
       cycle_id = response.active_cycle_id
       continue with progress packets against cycle_id
   else:
       # the prior cycle is stuck. Retry with force.
       POST /washing/device-start  {"mode": ..., "force": true}
```

This handles all three race patterns cleanly:
- App-first / device-second (within ~seconds) → device adopts, no destructive force.
- Device-first / app-second → app gets the same 409 shape and can show the user "Wash is already running" instead of an error.
- Truly simultaneous → the server holds a per-device advisory lock around the start path, so exactly one start wins; the other gets the 409 shape above. No more dual-insert risk.

#### Recovery from a stuck cycle

A cycle can get stuck in `pending`/`running` if the firmware crashed
mid-cycle, lost network before sending its completion packet, or never
came back online. There are two recovery paths — both supported:

1. **Firmware-driven (immediate):** retry with `"force": true`. The
   stuck cycle is flipped to `failed` and the new cycle is created in
   the same call. The WS broadcast that goes to app clients includes a
   `superseded_cycle_id` field so the app can clean up any state
   pinned to the old cycle id.

   ```json
   { "mode": "full_cycle", "force": true }
   ```

2. **Server-driven (safety net):** every 5 minutes a scheduler job
   auto-fails any cycle that's been in `pending` or `running` state for
   more than **60 minutes** (longer than the longest legitimate wash).
   This guarantees nothing stays stuck forever, even if the firmware
   never gets a chance to retry.

The HTTP-side `POST /washing/start` (app path) intentionally does *not*
support `force`. Cleanup from the app side is meant to be explicit so
users don't accidentally cancel a wash that's still running on the
machine.

---

### 4i. Start a Dispense from the Device (physical controls)

Use this when the user dials temperature + volume on the **device's own
controls** and triggers a dispense. Mirrors §4h.

```
POST /dispensing/device-start
Header: X-Device-Api-Key: <api_key>
Content-Type: application/json
```

Request body:

```json
{ "temperature_c": 37.0, "volume_ml": 120, "force": false }
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `temperature_c` | Yes | float | 20.0 – 45.0 (safe milk range). |
| `volume_ml` | Yes | float | 10.0 – 300.0. |
| `force` | No | bool | Default `false`. When `true`, any prior pending/dispensing log on this device is force-failed. Same recovery semantics as §4h. |

Response `201 Created`:

```json
{
  "id": 17,
  "device_id": 7,
  "temperature_c": 37.0,
  "volume_ml": 120.0,
  "status": "pending",
  "progress_pct": 0,
  "initiated_by": "device",
  "created_at": "2026-05-24T19:42:00",
  "completed_at": null
}
```

Store `id` locally — that's the `log_id` you echo back in subsequent
`POST /dispensing/progress` calls (see §4b).

**Concurrency rule:** same as §4h. A device can have only one active
dispense at a time; otherwise `409 Conflict` with details about the
active log:

```json
{
  "detail": "A dispense is already active on this device. If it's stale, resend with `force: true`; if it just started (see active_log_created_at), adopt its `active_log_id` for subsequent progress packets.",
  "active_log_id": 17,
  "active_log_created_at": "2026-05-28T22:42:00",
  "active_log_initiated_by": "app",
  "active_log_status": "pending",
  "active_log_temperature_c": 37.0,
  "active_log_volume_ml": 120.0
}
```

Apply the same adopt-vs-force logic as §4h: if `active_log_created_at`
is within the last few seconds, adopt the existing `active_log_id` for
your progress packets; otherwise force a replacement.

**Stale safety net:** the same scheduler job that recovers stuck wash
cycles also recovers stuck dispense logs. The dispense timeout is
**15 minutes** (much tighter than wash because dispensing is short).
Any dispense in `pending`/`dispensing` state for longer than that gets
auto-flipped to `failed`.

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
| 2026-05-24 | Added §4d `GET /devices/commands/pending` — HTTP polling alternative to WebSocket for receiving commands. Firmware may use either transport. |
| 2026-05-24 | Added §4e `POST /alerts/` documentation. Closed set of four safety `alert_type` values per MOU Annexure A1: `overheating`, `malfunction`, `washing_error`, `low_detergent`. |
| 2026-05-24 | Device API keys are now stored as SHA-256 hashes server-side. The plaintext key the firmware sends is unchanged — no firmware update required. |
| 2026-05-25 | Added §4f `POST /metrics/` and §4g `POST /activity/` documentation, plus a §3 explanation of why `cycle_id` / `log_id` are required on progress updates. |
| 2026-05-26 | Added §4h `POST /washing/device-start` and §4i `POST /dispensing/device-start` — device-initiated paths for when the user operates the physical machine directly. Server enforces only one active wash/dispense per device (`409 Conflict` otherwise). New `initiated_by` field in cycle/log responses. |
| 2026-05-28 | WS no longer echoes the sender's own events. |
| 2026-05-28 | WS events `wash_progress`, `dispense_progress`, `alert`, `metric` now **persist to the database** (full parity with the equivalent HTTP routes). Validation failures return an `error` frame to the sender and are not broadcast. WS `alert` now requires `alert_type` from the §4e catalog. |
| 2026-05-28 | Stuck-cycle recovery: `/washing/device-start` and `/dispensing/device-start` accept `force: true` to abandon a prior pending/running operation and start fresh. Scheduler also auto-fails wash cycles stale > 60 min and dispenses stale > 15 min. App-path `/washing/start` and `/dispensing/` stay strict (no force). |
| 2026-05-28 | 409 responses on every start endpoint now include `active_cycle_id`/`active_log_id` plus `*_started_at`/`*_created_at`, `*_initiated_by`, `*_status` so the firmware can adopt the existing operation instead of always force-replacing. Server also holds a per-device MySQL advisory lock around the check-then-insert path to eliminate the TOCTOU race when two starts arrive simultaneously. |
