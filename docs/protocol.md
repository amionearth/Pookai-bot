# PookalBot Communication Protocol

**Transport:** UART serial, 115200 baud, 8N1  
**Framing:** Line-delimited JSON — one JSON object per `\n`-terminated line  
**Direction:** Pi → ESP32 for commands, ESP32 → Pi for status

---

## Pi → ESP32 Commands

### drive
Move the robot by setting left/right motor speeds for a duration.

```json
{"cmd": "drive", "left": 150, "right": 150, "duration_ms": 500}
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| left | int | -255 to 255 | Left motor PWM (negative = reverse) |
| right | int | -255 to 255 | Right motor PWM (negative = reverse) |
| duration_ms | int | > 0 | Run duration in milliseconds, then stop |

---

### clean_start
Start a cleaning sequence in the specified mode.

```json
{"cmd": "clean_start", "mode": "pre"}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| mode | string | `pre` \| `post_no_exclude` \| `wet` | `pre` = dry pre-clean, `post_no_exclude` = dry post-clean (full area), `wet` = wet mop clean |

---

### turret_home
Send the chalk turret to its home (origin) position.

```json
{"cmd": "turret_home"}
```

No additional fields.

---

### turret_move
Move the chalk turret to a polar coordinate.

```json
{"cmd": "turret_move", "theta": 1.5708, "r": 120.0}
```

| Field | Type | Description |
|-------|------|-------------|
| theta | float | Angle in radians (0 = forward) |
| r | float | Radial distance in mm from turret center |

---

### pen
Raise or lower the chalk pen.

```json
{"cmd": "pen", "state": "down"}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| state | string | `up` \| `down` | `up` = pen lifted, `down` = pen on surface |

---

### estop
**Emergency stop.** Immediately halts all motors. Handled at the top of the ESP32 main loop before any other command is processed.

```json
{"cmd": "estop"}
```

No additional fields. The ESP32 checks for this command string before deserializing anything else.

---

## ESP32 → Pi Status

Sent approximately every 200 ms regardless of command activity.

```json
{"status": "ok", "phase": "idle", "turret_theta": 0.0, "turret_r": 0.0, "battery_mv": 7400, "obstacle": false}
```

| Field | Type | Description |
|-------|------|-------------|
| status | string | `ok` or `error` |
| phase | string | Current firmware phase/state (e.g. `idle`, `driving`, `drawing`, `cleaning`, `estopped`) |
| turret_theta | float | Current turret angle in radians |
| turret_r | float | Current turret radial position in mm |
| battery_mv | int | Battery voltage in millivolts |
| obstacle | bool | `true` if proximity sensor detects an obstacle |

---

## Error Handling

- Unknown or malformed JSON: ESP32 ignores the line and continues.
- Pi receives malformed JSON status: logs the line and skips it, does not crash.
- `estop` is checked via a simple `strstr` substring scan on the raw line **before** JSON parsing, so it fires even if the parser is slow or the queue is backed up.
