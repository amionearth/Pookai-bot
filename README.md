# PookalBot 🌸

> AI-Powered Autonomous Pookalam Robot — ThinkerHub Onam Edition
>
> **This repo implements the web app layer** (Steps 1–5 below). The
> ML/control service (localization, path-following, ESP32) lives in a
> separate process — `POST /api/robot/send` is the seam between them.

---

## What the web app does

```
[Prompt] → Gemini image gen → [Select] → CV vectorize → [Live View] → [Send]
   1            ↓                2           ↓              ↓           ↓
            2–3 PNGs        pick one     waypoint path   camera+ML   to robot
                                                        overlays
```

The web layer's job ends the moment the vector path is handed off. After
"Send to Robot", everything — ArUco localization, mouse odometry, the
path-following control loop, the ESP32/WiFi link — is the separate
ML/control service's responsibility.

The **Live View** step shows the camera feed with ML overlays (planned
path, robot position, drawing progress) and a state panel. It polls
`/api/live/state` ~5×/sec. There's a built-in demo simulator that walks
a virtual robot through the waypoints — useful for demoing without
hardware.

---

## Project structure

```
├── ai/                  # Gemini image gen + image validation
│   ├── gemini_client.py     # → Gemini multimodal, parallel candidates
│   ├── generator.py         #   top-level entry, drops bad candidates
│   └── models.py            #   pydantic schemas
├── cv/                  # Image → drawable path
│   ├── vectorize.py         # NEW: pixel→Cartesian cm (Step 5/6 of the build)
│   ├── path_gen.py          # LEGACY: pixel→polar (kept for the old build)
│   ├── preprocess.py
│   ├── circle_detect.py
│   ├── symmetry.py
│   └── cli.py
├── server/              # FastAPI — the web app's HTTP surface
│   ├── main.py
│   ├── models.py            # 4-step request/response shapes
│   └── routes/
│       ├── designs.py       # /api/designs/generate | /select | /vectorize
│       ├── camera.py        # /api/camera/stream   (MJPEG, <img src=...>)
│       └── robot.py         # /api/robot/send      (forwards to control svc)
├── web/static/          # Frontend — single page, 4 progressive steps
│   ├── index.html
│   ├── style.css            # Onam theme (Kasavu ivory/gold + Fraunces/Work Sans/Plex Mono)
│   └── app.js               # 4-step state machine
└── docs/                # Architecture + protocol specs
```

---

## Quick start

### Install

```bash
pip install -r requirements.txt
```

### Configure

```bash
# PowerShell
$env:GEMINI_API_KEY = "AIzaSy..."

# bash
export GEMINI_API_KEY=AIzaSy...
```

Without a key, `/api/designs/generate` returns 503 — the rest of the
app still loads, the health badge in the header says "No API key" in red.

### Run the server

```bash
# Dev (auto-reload, localhost only)
python -m uvicorn server.main:app --reload

# Hackathon demo (on the Pi, reachable from other devices on the same WiFi)
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
# Then open http://raspberrypi.local:8000 from any device on the same WiFi
```

API docs → `http://<host>:8000/docs`

### Optional: forward to the control service

```bash
$env:POOKALBOT_CONTROL_URL  = "http://127.0.0.1:9000"   # where the ML/control service listens
$env:POOKALBOT_CONTROL_TOKEN = "shared-secret-if-any"
```

Without `POOKALBOT_CONTROL_URL`, `/api/robot/send` still acks the
payload — useful for end-to-end testing of the web app before the
control service exists.

### Optional: pick a different camera

```bash
$env:POOKALBOT_CAMERA_INDEX = "0"   # default
```

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/designs/generate`  | Step 1 — 2–3 Pookalam candidates from Gemini |
| `POST` | `/api/designs/select`    | Step 2 — pick one (persists server-side) |
| `POST` | `/api/designs/vectorize`  | Step 3 — image → Cartesian-cm waypoints, side-by-side previews |
| `GET`  | `/api/camera/stream`      | Step 4 — live MJPEG (drop into `<img src=...>`) |
| `GET`  | `/api/camera/status`      | Camera availability probe |
| `GET`  | `/api/live/state`         | Step 4 — robot pose, drawing progress, pen, etc. |
| `POST` | `/api/live/state`         | Control service pushes its state here (called by the ML service) |
| `POST` | `/api/live/simulate/start`| Start the demo simulator (no hardware needed) |
| `POST` | `/api/live/simulate/stop` | Stop the demo simulator |
| `POST` | `/api/robot/send`         | Step 5 — hand the path off to the control service |
| `GET`  | `/api/robot/status`       | Most recent status from the control service |
| `GET`  | `/api/health`             | Server + Gemini availability |

### Request shapes

```jsonc
// POST /api/designs/generate
{
  "petal_count": 6,        // 4 | 5 | 6 | 8 | 10 | 12
  "layer_count": 2,        // 1 | 2 | 3
  "color_count": 3,        // 2 | 3 | 4 | 5
  "free_text":   "traditional Kerala lotus"   // optional, ≤ 500 chars
}

// POST /api/designs/vectorize
{
  "design_id": "uuid-...",
  "canvas_cm": 60          // real-world edge length of the drawing area
}

// POST /api/robot/send
{
  "design_id": "uuid-...",
  "canvas_cm": 60,
  "waypoints": [{"x": 1.2, "y": -0.3, "pen": 1}, ...]
}
```

---

## The Onam theme

Palette, typography, and layout are deliberately tied to the subject
itself — a pookalam is built ring-by-ring from the centre outward, and
the step-progress at the top of the page is a tiny 4-ring pookalam
that gains one ring per completed step. By Step 4 it's visually become
the thing the robot is about to draw.

| Token | Value | Use |
|---|---|---|
| Kasavu ivory | `#FAF0DC` | page background |
| Kasavu gold  | `#C89B3C` | primary accent, step-number, header rule |
| Banana-leaf green | `#3F6B35` | "vectorization complete," success states |
| Kumkum red   | `#B7282E` | primary CTAs (Generate, Send to Robot) |
| Deep dusk teal | `#1F3A3D` | body text |
| Marigold     | `#E8A33D` | small accents only |

Display: **Fraunces** · Body: **Work Sans** · Data readouts: **IBM Plex Mono**.

---

## Hosting notes (for demo day)

- Bind to `0.0.0.0` (not `localhost`) so other devices on the same WiFi
  can reach the Pi.
- Use a predictable address: either a static IP on your router, or
  rely on mDNS (`raspberrypi.local`) — avoids hunting for an IP
  mid-demo.
- **Client isolation**: many public/guest WiFi networks block
  device-to-device traffic even on the same SSID. Test at the venue
  beforehand, or bring a small travel router as a fallback.
- No auth, no HTTPS, no database — everything in-memory is fine for a
  single-session demo.

---

## Tests

```bash
python -m pytest ai/tests/     -v    # Gemini client (offline, no key needed)
python -m pytest cv/tests/     -v    # CV pipeline (offline)
```

---

## Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `GEMINI_API_KEY`          | Gemini image generation | No — app runs, but `/generate` returns 503 |
| `AI_API_KEY`              | Legacy alias for `GEMINI_API_KEY` | No |
| `POOKALBOT_CAMERA_INDEX`  | OpenCV camera index (default `0`) | No |
| `POOKALBOT_CONTROL_URL`   | Where to forward `/api/robot/send` (the ML/control service) | No |
| `POOKALBOT_CONTROL_TOKEN` | Bearer token for the control service | No |
