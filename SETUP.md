# PookalBot — Complete Setup Guide

> A from-scratch guide to getting the whole robot working on a Raspberry Pi + ESP32.
> Written for a complete beginner — every command, every wire, every gotcha.

---

## Table of contents

- [0. The big picture](#0-the-big-picture)
- [1. Shopping list](#1-shopping-list)
- [2. Prepare the Pi (headless)](#2-prepare-the-pi-headless)
- [3. First Pi config](#3-first-pi-config)
- [4. Set up the project on the Pi](#4-set-up-the-project-on-the-pi)
- [5. Get a Gemini API key](#5-get-a-gemini-api-key)
- [6. Run the server](#6-run-the-server)
- [7. Add the camera](#7-add-the-camera)
- [8. Gut the mouse for the robot](#8-gut-the-mouse-for-the-robot)
- [9. Flash the ESP32](#9-flash-the-esp32)
  - [9.1 Install Arduino IDE](#91-install-arduino-ide)
  - [9.2 Add ESP32 board support](#92-add-esp32-board-support)
  - [9.3 Install libraries](#93-install-libraries)
  - [9.4 Configure TFT_eSPI (User_Setup.h)](#94-configure-tft_espi-usersetuph)
  - [9.5 Configure the firmware](#95-configure-the-firmware)
  - [9.6 Upload](#96-upload)
- [10. Build + wire the robot](#10-build--wire-the-robot)
- [11. Network setup](#11-network-setup)
- [12. First end-to-end test](#12-first-end-to-end-test)
- [13. Troubleshooting](#13-troubleshooting)
- [14. Ready-for-demo checklist](#14-ready-for-demo-checklist)
- [Appendix A: ESP32 firmware (full source)](#appendix-a-esp32-firmware-full-source)

---

## 0. The big picture

```
┌──────────────────────────┐        ┌────────────────────────┐
│  Your laptop / phone     │  HTTP  │  Raspberry Pi          │
│  (browser)               │ ─────► │  - FastAPI server      │
│  - Prompt                │        │  - Gemini API call     │
│  - Pick a design         │        │  - CV vectorize        │
│  - Watch camera          │        │  - Camera stream       │
│  - Press Send            │        │  - (later) Localization│
│  - See Kathakali eyes    │        │  - (later) Path follower│
└──────────────────────────┘        └────────┬───────────────┘
                                             │ UDP over WiFi
                                             ▼
                                    ┌────────────────────────┐
                                    │  ESP32 (on the robot)  │
                                    │  - WiFi + UDP receiver │
                                    │  - L298N → 2 DC motors │
                                    │  - Servo for pen lift  │
                                    │  - TFT → Kathakali eyes│
                                    │  - Mouse sensor (RO)   │
                                    └────────────────────────┘
```

Two computers that talk over WiFi. The Pi is stationary, ESP32 is on the robot. Nothing else talks between them.

---

## 1. Shopping list

Roughly ₹6,000–8,000 / ~$80–100 for the whole thing if you don't have any of it.

### Stationary (Pi side — sits on a tripod/stand)

| Item | Notes | India (rough) | Global |
|---|---|---|---|
| Raspberry Pi 4 (2GB) | 4GB nicer, 2GB works | ₹4,000–5,000 | $35–45 |
| Pi camera OR USB webcam | USB webcam easier for first test | ₹400–800 | $5–10 |
| MicroSD card 16GB+ | Class 10 | ₹400 | $8 |
| USB-C power supply (5V 3A) | Official Pi PSU is best | ₹600 | $10 |
| Small tripod/stand for camera | Holds camera ~2 m above the floor | ₹300 | $5 |
| **Wireless USB mouse** (any cheap one) | You'll gut the sensor half — see §8 | ₹250 | $4 |

### Robot side (moves around)

| Item | Notes | India | Global |
|---|---|---|---|
| ESP32 DevKit (any 30-pin) | Must have WiFi (all DevKits do) | ₹350 | $5 |
| 2× DC gear motors + wheels | 6V or 12V, ~100–200 RPM is good | ₹400 | $5 |
| 1× caster wheel (front or back) | Standard 2WD+caster | ₹80 | $1 |
| L298N or TB6612FNG motor driver | L298N is cheap and forgiving | ₹150 | $2 |
| 1× SG90 or MG90S servo | Pen-lift | ₹150 | $2 |
| 1× ArUco marker (printed) | Print on paper, glue to cardboard. See §10 | free | free |
| 1× battery pack for motors | 4×AA holder or 2S Li-ion. **Separate from Pi power** | ₹150 | $3 |
| 1× battery pack for ESP32 | USB powerbank or small LiPo + boost converter | ₹300 | $4 |
| 1.8" 128×160 ST7789 SPI TFT | The "Kathakali eyes" display | ₹300 | $4 |
| Chassis (3D-printed, laser-cut, or cardboard) | 10×10 cm plate with motor mounts is enough | varies | varies |
| Jumper wires (M-F, M-M) | At least 20 | ₹100 | $2 |
| Breadboard | Half-size | ₹80 | $2 |
| **E-stop button** (recommended) | Normally-closed, in series with motor power | ₹50 | $1 |

**Order from** (India): Robu.in, electronicscomp.com, Amazon.in, QuartzComponents, Sunrom. Search the part name — they all stock the common stuff.

**Skip the parts you already have.** Minimum viable: Pi + camera + ESP32 + 2 motors + 1 caster + 1 servo + 1 mouse + 1 battery + 1 TFT.

---

## 2. Prepare the Pi (headless — no monitor needed)

### 2.1 Download Pi Imager

Get it from https://www.raspberrypi.com/software/ — works on Windows/Mac/Linux.

### 2.2 Flash the SD card

1. Put the microSD in your laptop (use an adapter if needed).
2. Open Pi Imager.
3. **Choose Device** → "Raspberry Pi 4".
4. **Choose OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)** — Lite has no desktop, which is what you want.
5. **Choose Storage** → your SD card.
6. Click **Next** → Pi Imager will ask "Use OS customisation?" → click **EDIT SETTINGS**.

In the customisation popup:

**General tab:**
- Hostname: `raspberrypi` (or `pookalpi`)
- Username: `pi` (or your choice)
- Password: pick one, remember it
- WiFi SSID + Password: **your 2.4 GHz WiFi only** — ESP32 doesn't do 5 GHz
- WiFi country: India (or wherever you are)
- Locale: Asia/Kolkata, en_IN (or your locale)

**Services tab:**
- ☑ Enable SSH → "Use password authentication"

**Options tab:**
- ☑ Set telemetry to OFF (Pi Imager may not ask — no big deal if it does)

Click **Save**, then **Yes** to apply. Pi Imager will write + verify (~5–10 min).

### 2.3 Boot the Pi

1. Eject the SD card, put it in the Pi.
2. Plug in the USB-C power.
3. Wait 60 s (green LED flickers while it boots).

### 2.4 Find the Pi on your network

From your laptop's terminal:

```bash
# mDNS works on most home routers
ssh pi@raspberrypi.local
```

If that fails (some Windows networks and public WiFi block mDNS), find the IP from your router's admin page, then:

```bash
ssh pi@192.168.1.42   # whatever IP the router assigned
```

If `ssh` isn't found:
- Windows 10/11: Settings → Apps → Optional features → Add → "OpenSSH Client"
- Mac / Linux: already installed

Accept the host-key fingerprint prompt, type your password. You're in. 🎉

---

## 3. First Pi config

```bash
# 3.1 Update the OS (reboot after)
sudo apt update && sudo apt full-upgrade -y
sudo reboot
# wait 30s, ssh back in

# 3.2 Install the system packages we need
sudo apt install -y python3 python3-venv python3-pip git build-essential \
    libatlas-base-dev libjpeg-dev libpng-dev libavcodec-dev libavformat-dev \
    libswscale-dev libv4l-dev libxvidcore-dev libx264-dev

# 3.3 Enable camera interfaces
sudo raspi-config
# → Interface Options → Camera → Yes
# → Interface Options → I2C  → Yes  (for some IMUs, optional for us)
# → Finish → Yes to reboot
```

> **Why all those `lib*-dev` packages?** OpenCV's Python wheel ships with most things pre-compiled, but a few of its optional features want system headers. Cheap insurance against weird import errors later.

---

## 4. Set up the project on the Pi

Easiest if the project is in a git repo. If not, copy via `scp` from your laptop:

```bash
# From your LAPTOP, in the parent directory of `mosaic/`:
scp -r mosaic pi@raspberrypi.local:~/

# ssh back in
ssh pi@raspberrypi.local
cd ~/mosaic
```

Or with git:

```bash
git clone https://github.com/your-team/pookalbot.git
cd pookalbot/mosaic
```

### 4.1 Create a virtual env

**Always** use a venv on the Pi. Don't `pip install` to system Python.

```bash
cd ~/mosaic          # or wherever you copied the project to
python3 -m venv .venv
source .venv/bin/activate
# Your prompt should now start with (.venv)

python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs FastAPI, OpenCV, Pillow, httpx, pytest, etc. Takes 2–5 min on a Pi 4.

> If you ever close the terminal and come back, re-run `source .venv/bin/activate` before any python command.

---

## 5. Get a Gemini API key

Since this is a Google Hackathon, this is free.

1. Open https://aistudio.google.com/apikey in any browser.
2. Sign in with the Google account you used for the hackathon.
3. Click **"Create API key"** → copy the key (starts with `AIza...`).
4. On the Pi, save it permanently:

```bash
echo 'export GEMINI_API_KEY="AIzaSyYourKeyHere"' >> ~/.bashrc
source ~/.bashrc

# Verify
echo $GEMINI_API_KEY
# should print AIzaSyYourKeyHere
```

> Gemini 2.0 Flash with image gen is generous on the free tier. A hackathon demo will generate maybe 50–100 designs. You won't hit a bill.

---

## 6. Run the server

```bash
cd ~/mosaic
source .venv/bin/activate
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 6.1 Test from your laptop

Open `http://raspberrypi.local:8000` in a browser on the same WiFi.

You should see the Onam-themed page with **Step 1 — Describe your pookalam**. The health badge in the top-right should say **"Gemini ready"** (green). If it says **"No API key"** (red), the env var didn't stick — redo §5.

### 6.2 Test from the Pi itself (no browser needed)

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"pookalbot","ai_available":true,"mode":"ai"}

curl -X POST http://localhost:8000/api/designs/generate \
    -H "Content-Type: application/json" \
    -d '{"petal_count":6,"layer_count":2,"color_count":3,"free_text":"lotus"}'
# If this returns 3 designs → everything works.
```

> If `curl` hangs, your laptop and Pi are on different WiFi networks. Both need to be on the same 2.4 GHz SSID.

### 6.3 Keep the server running after you close the terminal

For dev: just leave the terminal open.

For demo day, use `tmux` so it survives terminal disconnects:

```bash
sudo apt install -y tmux
tmux new -s server
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+B then D to detach.  Later: tmux attach -t server
```

---

## 7. Add the camera

**USB webcam is easier — start with that.**

### USB webcam

1. Plug into any Pi USB port.
2. Check it works:

   ```bash
   ls /dev/video*
   # should show /dev/video0 (and maybe /dev/video1, /dev/video2)
   ```

3. Restart the server, then in a browser: `http://raspberrypi.local:8000/api/camera/status` should return `{"available": true, "index": 0}`.

4. In the app, go to **Step 4** — you should see the live feed in the camera frame.

> If "unavailable": try `POOKALBOT_CAMERA_INDEX=1` (or 2, 3...) and restart the server.

### Pi Camera Module (CSI ribbon)

1. With the Pi **off**, plug the ribbon into the CSI port (blue side facing the Ethernet jack on a Pi 4).
2. `sudo raspi-config` → Interface Options → Camera → Enable → reboot.
3. Test: `libcamera-hello` (5-second preview).
4. For OpenCV via V4L2: add `dtoverlay=imx219` (or your sensor) to `/boot/config.txt`, then reboot.

USB webcam is genuinely easier. Use it.

---

## 8. Gut the mouse for the robot

This is the weirdest part. The robot needs a relative-position sensor, and a $4 wireless mouse gives you one for free.

### 8.1 Disassemble

1. Take your cheap wireless mouse.
2. Open it (usually 2–4 screws under the battery + the glide pads).
3. Find the small PCB with the camera/sensor (a tiny black box, usually labeled "PAN3204" or similar).
4. The PCB has 4–6 wires: VCC (red), GND (black), and data lines.

### 8.2 Re-house the sensor

The sensor needs to:
- Be 1–3 mm above the floor
- Point straight DOWN
- Be level (not tilted)
- Move with the robot

A 3D-printed "sled" is ideal. For cardboard:
- Cut a small cardboard plate (~3 cm × 3 cm).
- Hot-glue the sensor PCB to it, sensor facing down.
- Hot-glue this plate to the underside of the robot chassis, sensor ~2 mm above the floor.

### 8.3 Plug the dongle into the Pi

**The USB dongle goes in the Pi, not the robot.** The sensor PCB rides on the robot, transmits wirelessly to the dongle on the Pi. The Pi reads the mouse motion as a relative `(dx, dy)` per frame.

> **Matte surface only.** The sensor can't track on glossy or transparent floors. Test on the actual floor you'll draw on. If it slips, put a sheet of kraft / chart paper down.

Sanity check that the sensor is alive:

```bash
sudo apt install -y evtest
sudo evtest
# Pick the mouse device → move the sensor by hand → you should see REL_X/REL_Y events
```

---

## 9. Flash the ESP32

The firmware in `mosaic/esp32/pookalbot_firmware.ino` controls the motors, servo, and TFT, and listens for UDP commands from the Pi.

### 9.1 Install Arduino IDE

On your **laptop** (not the Pi):
- Download from https://www.arduino.cc/en/software
- Open it.

### 9.2 Add ESP32 board support

- File → Preferences → "Additional boards manager URLs" → add:
  `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
- Tools → Board → Boards Manager → search "esp32" → Install.

### 9.3 Install libraries

Sketch → Include Library → Manage Libraries → install:
- **ArduinoJson** (v6.x)
- **ESP32Servo**
- **TFT_eSPI**

### 9.4 Configure TFT_eSPI (User_Setup.h)

TFT_eSPI needs to know which display + which pins you have.

1. Find the library folder:
   - **Windows:** `Documents\Arduino\libraries\TFT_eSPI\`
   - **Mac:** `~/Documents/Arduino/libraries/TFT_eSPI/`
   - **Linux:** `~/Arduino/libraries/TFT_eSPI/`

2. Open `User_Setup.h` in a text editor.

3. Replace its contents with the config for a generic 1.8" ST7789:

   ```cpp
   // ─── User_Setup.h — generic 1.8" 128x160 ST7789 ────────────────
   #define ST7789_DRIVER
   #define ST7789_128
   #define TFT_WIDTH  128
   #define TFT_HEIGHT 160

   // Pin map (matches the firmware)
   #define TFT_MOSI   23
   #define TFT_SCLK   18
   #define TFT_CS      5
   #define TFT_DC      2
   #define TFT_RST     4
   #define TFT_BL     15

   // Fonts you want to load (optional — keep small to save flash)
   #define LOAD_GLCD
   #define LOAD_FONT2
   #define LOAD_FONT4
   #define LOAD_FONT6
   #define LOAD_FONT7
   #define LOAD_FONT8
   #define LOAD_GFXFF
   #define SMOOTH_FONT
   ```

4. Save and **restart the Arduino IDE** (it caches the old config).

> If you have a different display (ILI9341, etc.), use the matching `User_Setup.h` from TFT_eSPI's `Setup<XXX>_*.h` examples and adjust the pin numbers.

### 9.5 Configure the firmware

Open `mosaic/esp32/pookalbot_firmware.ino` in the Arduino IDE. Edit the **CONFIGURATION** block at the top:

```cpp
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* PI_IP         = "192.168.1.50";   // the Pi's static IP, see §11
const int   PI_PORT       = 9000;
const int   LOCAL_UDP_PORT= 9000;

// After you mount the pen, measure these by hand
const int PEN_UP_ANGLE    = 0;
const int PEN_DOWN_ANGLE  = 70;
```

If one motor spins backwards after you wire it up, flip the matching `INVERT_LEFT` / `INVERT_RIGHT` flag.

### 9.6 Upload

1. Plug the ESP32 into your laptop via USB.
2. Tools → Board → ESP32 Dev Module.
3. Tools → Port → (the COM port that appears).
4. Click Upload (→ arrow).

> **First-flash gotcha:** some ESP32 clones need the **BOOT** button held while uploading. If the first upload fails with "Failed to connect", hold BOOT, click Upload, release BOOT when the serial port resets.

When the upload succeeds, open the Serial Monitor (115200 baud) and you should see:

```
=== PookalBot firmware v2 ===
Connecting to YOUR_WIFI_SSID........
WiFi connected. IP: 192.168.1.77
UDP listening on port 9000, target 192.168.1.50:9000
Ready.
```

The TFT should come alive with two Kathakali eyes glancing side to side.

---

## 10. Build + wire the robot

### 10.1 Wiring diagram

```
                        ┌──────────────────────┐
   Motor battery (+) ──►│ L298N                │◄── Motor battery (−)
                        │                      │
   ESP32 GPIO 25 ──────►│ IN1  OUT1 ───────────►│ Left  motor (+)
   ESP32 GPIO 26 ──────►│ IN2  OUT2 ───────────►│ Left  motor (−)
   ESP32 GPIO 27 ──────►│ ENA                   │   (PWM speed)
                        │                      │
   ESP32 GPIO 32 ──────►│ IN3  OUT3 ───────────►│ Right motor (+)
   ESP32 GPIO 33 ──────►│ IN4  OUT4 ───────────►│ Right motor (−)
   ESP32 GPIO 14 ──────►│ ENB                   │   (PWM speed)
                        │                      │
   ESP32 5V ────────────►│ +5V (logic)           │
   ESP32 GND ───────────►│ GND                   │  (common with motors)
                        └──────────────────────┘

   ESP32 GPIO 13 ──► Servo signal (orange)
   ESP32 5V ──────► Servo VCC (red)
   ESP32 GND ─────► Servo GND (brown)

   ESP32 GPIO 18/23/5/2/4/15 ──► ST7789 TFT (SCLK/MOSI/CS/DC/RST/BL)
   ESP32 3.3V ─────► TFT VCC
   ESP32 GND ──────► TFT GND
```

> **Common ESP32 + motor gotcha:** motor startup spikes can reset the ESP32. **Decouple supplies** — the motor battery and the ESP32's USB power are SEPARATE. Common ground only between L298N and ESP32.

### 10.2 Mechanical build order

1. **Chassis** — 10 × 10 cm plate. Mount the 2 motors at the back, caster at the front.
2. **Motor driver** — L298N stuck to the chassis with double-sided tape.
3. **ESP32 + breadboard** — on top of the chassis.
4. **Battery pack** — zip-tied underneath.
5. **Servo + pen** — at the front, servo arm holds a marker pointing down.
6. **Mouse sensor sled** — hot-glued underneath, ~2 mm above the floor.
7. **ArUco marker** — printed, glued to a 5 × 5 cm cardboard square, mounted FLAT on top of the robot, parallel to the floor, centered. Make sure the camera can see it from above.

### 10.3 Print the ArUco marker

On the Pi (or your laptop):

```python
import cv2
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker = cv2.aruco.generateImageMarker(aruco_dict, 0, 200)  # id=0, 200 px
cv2.imwrite("aruco_0.png", marker)
```

Print `aruco_0.png` at ~5 × 5 cm. Mount it on the robot top.

---

## 11. Network setup

- **Same 2.4 GHz WiFi** for the Pi and the ESP32. ESP32 doesn't do 5 GHz.
- **mDNS works on most home routers** but not all. Have the Pi's IP as backup:
  ```bash
  hostname -I    # shows the Pi's IP
  ```
- **No client isolation** — many public/guest WiFi networks block device-to-device traffic. Test at the venue beforehand, or bring a small travel router.

### Give the Pi a static IP

```bash
# Get your current gateway
ip route | grep default

# Set a static IP (use values that match your network)
sudo nmcli con mod "preconfigured" ipv4.addresses 192.168.1.50/24
sudo nmcli con mod "preconfigured" ipv4.gateway 192.168.1.1
sudo nmcli con mod "preconfigured" ipv4.dns "8.8.8.8 1.1.1.1"
sudo nmcli con mod "preconfigured" ipv4.method manual
sudo nmcli con up "preconfigured"

# Verify
ip addr show wlan0 | grep inet
```

Then in the firmware, set `PI_IP` to that static IP.

---

## 12. First end-to-end test

Always test the smallest piece first.

### Test 1: Web app
- Open `http://raspberrypi.local:8000` on your laptop.
- Health badge is green.
- Step 1 → Generate → 3 designs appear within 10 s.

### Test 2: Vectorize
- Select a design → Step 3 side-by-side preview shows up → waypoint count > 0.

### Test 3: Camera
- Step 4 → live feed visible. Hold a piece of paper in front of the camera.

### Test 4: Robot drives (open-loop, no localization)
- Place the robot on the floor with the pen lifted.
- From the Pi, send raw UDP packets and watch the robot move:
  ```bash
  # Install a quick UDP sender
  sudo apt install -y ncat

  # Drive forward at 80/255 for 2 seconds
  for i in $(seq 1 20); do
    echo '{"left":80,"right":80,"pen":0}'
  done | ncat -u -w 2 192.168.1.77 9000
  ```
  (Replace the IP with the ESP32's IP from Serial Monitor output.)

- **Test turning:** `{"left":80,"right":-80,"pen":0}` — should spin in place.
- **Test reverse:** `{"left":-80,"right":-80,"pen":0}` — should reverse.
- **Test pen:** `{"left":0,"right":0,"pen":1}` — servo should click down.

### Test 5: Closed loop
- Place the robot on the floor, ArUco marker visible to the camera.
- Trigger a small draw path (e.g. a 10 cm square) via the control loop.
- The robot should drive the square within ~1 cm of the requested corners.
- **Iterate from here** — tune the control gains, fix drift.

### Test 6: Real pookalam
- Generate a 4-fold, 2-color, 1-layer design (simplest).
- Select → vectorize → send.
- The robot should draw it. If it doesn't, you have a debug session ahead. This is normal.

---

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `GEMINI_API_KEY not set` in browser | Env var not loaded | `echo $GEMINI_API_KEY` on the Pi — if empty, redo §5 |
| 502 on /generate | Gemini returned no images | Check server logs. Usually safety filter blocked the prompt — try a different `free_text` |
| 503 on /generate | No API key | See above |
| Camera feed is black | Wrong index or camera not enabled | `ls /dev/video*`, set `POOKALBOT_CAMERA_INDEX` to the right one |
| `raspberrypi.local` not found | mDNS blocked | Use the IP. `ping raspberrypi.local` from laptop to test |
| ESP32 won't connect to WiFi | 5 GHz only | ESP32 only does 2.4 GHz — check your router settings |
| ESP32 keeps rebooting when motors spin | Power supply spike | Separate motor battery and ESP32 USB power. Common GND only. |
| Robot drifts left/right | Motor mismatch | Add a trim in the firmware (multiply one motor's PWM by 0.95) |
| Robot overshoots turns | Wheelbase estimate wrong | Measure the actual wheel-to-wheel distance, update in control code |
| Vectorize returns "no circle detected" | Gemini image isn't following the rules | Try regenerating, or lower `petal_count` |
| Mouse sensor returns weird values | Sensor too high or on glossy surface | Lower to 1–2 mm, put matte paper on the floor |
| TFT shows white / nothing | Wrong display type or wiring | Double-check `User_Setup.h` matches your display |
| TFT shows colors but garbled | SPI pins wrong | Check SCLK=18, MOSI=23, CS=5, DC=2, RST=4 |
| Servo jitters nonstop | Separate power issue | Add a 100 µF capacitor across the servo's VCC and GND |

---

## 14. Ready-for-demo checklist

Before the judges see it:

- [ ] Pi boots and the server starts automatically (use `tmux` or a systemd service)
- [ ] `http://raspberrypi.local:8000` opens in any browser on the venue WiFi
- [ ] Health badge is green (Gemini key is loaded)
- [ ] Generate → 3 designs appear within 10 s
- [ ] Select → vectorize runs in < 2 s
- [ ] Camera feed is live and clear
- [ ] Robot draws cleanly on the floor
- [ ] Backup demo video is recorded **before** the judges arrive
- [ ] E-stop button works (test it!)
- [ ] You have 2 spare batteries, fully charged
- [ ] You have a printed ArUco marker as a spare
- [ ] You know the venue WiFi password AND you've verified device-to-device traffic works

---

## Appendix A: ESP32 firmware (full source)

The full source is in [`mosaic/esp32/pookalbot_firmware.ino`](esp32/pookalbot_firmware.ino) — that's the file the Arduino IDE compiles. Reproduced here for reference so this guide is self-contained:

```cpp
/*
 * PookalBot Firmware v2 — Mobile 2WD + Pen Servo + Kathakali-eye TFT
 * ─────────────────────────────────────────────────────────────────────
 *
 * What this does
 * ───────────────
 *  - Connects to your home/venue 2.4 GHz WiFi
 *  - Listens for UDP commands from the Raspberry Pi
 *  - Drives 2 DC motors via an L298N (differential drive, PWM speed)
 *  - Lifts / lowers a chalk pen with a hobby servo
 *  - Drives a 1.8" 128x160 ST7789 SPI TFT, drawing two Kathakali
 *    eyes that slowly glance side-to-side, dart occasionally, and
 *    blink every few seconds. A green/red status dot in the corner
 *    shows WiFi state.
 *  - Watchdog: if no UDP packet for 250 ms, motors stop. Safety first.
 *
 * Protocol (UDP, JSON, one packet per line, ~10 Hz from the Pi)
 * ───────────────────────────────────────────────────────────
 *   {"left": -255..255, "right": -255..255, "pen": 0|1}
 *     left, right  : signed PWM duty. Sign = direction, magnitude = speed.
 *     pen          : 1 = pen down (drawing), 0 = pen up (travelling).
 *
 * Hardware
 * ─────────
 *   ESP32 DevKit (any 30-pin variant)
 *   L298N motor driver, 2 DC gear motors, 1 caster wheel
 *   SG90 / MG90S servo (pen lift)
 *   1.8" 128x160 ST7789 SPI TFT
 *   Wireless mouse sensor (gutted, mounted under the robot, see §8)
 *
 * Pin map
 * ────────
 *   Left  motor:  IN1=25  IN2=26  ENA=27  (PWM, 20 kHz, 8-bit)
 *   Right motor:  IN3=32  IN4=33  ENB=14  (PWM)
 *   Servo:        SIG=13
 *   TFT (ST7789): SCLK=18  MOSI=23  CS=5  DC=2  RST=4  BL=15
 *   Status LED:   onboard LED on GPIO 2 (heartbeat blink)
 *
 * Libraries (install via Arduino → Sketch → Include Library → Manage)
 * ──────────────────────────────────────────────────────────────────
 *   - ArduinoJson   (v6.x)
 *   - ESP32Servo
 *   - TFT_eSPI      (also requires User_Setup.h config — see §9.4)
 *
 *   Built-in: WiFi.h, WiFiUdp.h
 *
 * First flash
 * ───────────
 *   Some ESP32 clones need the BOOT button held during upload. See
 *   §9.6 if the first upload fails.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <TFT_eSPI.h>
#include <math.h>

// ╔══════════════════════════════════════════════════════════════════════╗
// ║                          CONFIGURATION                              ║
// ╚══════════════════════════════════════════════════════════════════════╝

// ── WiFi — must be 2.4 GHz, ESP32 doesn't do 5 GHz ────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ── Where the Pi lives (give the Pi a static IP — see §11) ──────────────
const char* PI_IP   = "192.168.1.50";
const int   PI_PORT = 9000;

// ── UDP port the Pi sends to (must match the Pi's UDP sender) ────────────
const int LOCAL_UDP_PORT = 9000;

// ── Pen-lift servo angles — measure these after mounting the pen ──────────
const int PEN_UP_ANGLE    = 0;     // pen lifted, free to travel
const int PEN_DOWN_ANGLE  = 70;    // pen pressing on the floor
const int PEN_TRANS_MS    = 200;   // smoothing time for the move (informational)

// ── Motor safety watchdog ─────────────────────────────────────────────────
const unsigned long MOTOR_TIMEOUT_MS = 250;  // stop if no UDP in this window

// ── Optional: invert motors if you wired them the other way around ────────
const bool INVERT_LEFT  = false;
const bool INVERT_RIGHT = false;


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                            PIN MAP                                   ║
// ╚══════════════════════════════════════════════════════════════════════╝

// Left motor (L298N)
const int PIN_LM_IN1 = 25;
const int PIN_LM_IN2 = 26;
const int PIN_LM_ENA = 27;   // PWM

// Right motor
const int PIN_RM_IN3 = 32;
const int PIN_RM_IN4 = 33;
const int PIN_RM_ENB = 14;   // PWM

// Servo
const int PIN_SERVO = 13;

// PWM channels (ESP32 LEDC peripheral)
const int PWM_CH_LM = 0;
const int PWM_CH_RM = 1;
const int PWM_FREQ  = 20000;   // 20 kHz — above audible range, quiet
const int PWM_RES   = 8;       // 8-bit → 0..255 matches the signed motor-speed range


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                            GLOBALS                                   ║
// ╚══════════════════════════════════════════════════════════════════════╝

WiFiUDP    udp;
Servo      penServo;
TFT_eSPI   tft = TFT_eSPI();

char packetBuf[256];
unsigned long lastCommandMs = 0;
bool         penIsDown      = false;

// Animation state
unsigned long bootMs        = 0;
unsigned long lastBlinkStart= 0;
bool   inBlink        = false;
float  eyePupilX      = 0.0;   // ±pixels from eye centre
float  eyeHeightScale = 1.0;   // 1.0 = open, 0.0 = closed

// TFT layout (128x160 ST7789 in landscape)
const int SCREEN_W     = 160;
const int SCREEN_H     = 128;
const int EYE_W        = 38;
const int EYE_H        = 26;
const int EYE_Y        = SCREEN_H / 2;
const int LEFT_EYE_X   = SCREEN_W / 2 - 22;
const int RIGHT_EYE_X  = SCREEN_W / 2 + 22;


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                              SETUP                                   ║
// ╚══════════════════════════════════════════════════════════════════════╝

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("=== PookalBot firmware v2 ===");
  bootMs = millis();

  setupMotors();
  setupServo();
  setupTFT();
  setupWiFi();

  Serial.println("Ready.");
}


void setupMotors() {
  pinMode(PIN_LM_IN1, OUTPUT);
  pinMode(PIN_LM_IN2, OUTPUT);
  pinMode(PIN_LM_ENA, OUTPUT);
  pinMode(PIN_RM_IN3, OUTPUT);
  pinMode(PIN_RM_IN4, OUTPUT);
  pinMode(PIN_RM_ENB, OUTPUT);

  ledcSetup(PWM_CH_LM, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_RM, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_LM_ENA, PWM_CH_LM);
  ledcAttachPin(PIN_RM_ENB, PWM_CH_RM);

  stopMotors();
}


void setupServo() {
  penServo.setPeriodHertz(50);
  // SG90-compatible pulse widths (microseconds). Adjust if your servo
  // doesn't reach the full range.
  penServo.attach(PIN_SERVO, 500, 2400);
  penServo.write(PEN_UP_ANGLE);
  penIsDown = false;
}


void setupTFT() {
  tft.init();
  tft.setRotation(1);                 // landscape
  tft.fillScreen(TFT_WHITE);
  drawKathakaliEyes(0.0f, 1.0f);      // initial frame: pupil centred
}


void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to %s", WIFI_SSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\nWiFi FAILED — will keep retrying in loop().");
  }

  udp.begin(LOCAL_UDP_PORT);
  Serial.printf("UDP listening on port %d, target %s:%d\n",
                LOCAL_UDP_PORT, PI_IP, PI_PORT);
}


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                          MOTOR HELPERS                               ║
// ╚══════════════════════════════════════════════════════════════════════╝

// Drive one motor channel. speed: -255..255 (sign = direction).
static inline void setMotor(int pwmChannel, int in1, int in2, int speed) {
  speed = constrain(speed, -255, 255);

  if (speed > 0) {
    digitalWrite(in1, HIGH);  digitalWrite(in2, LOW);
    ledcWrite(pwmChannel, (uint8_t)speed);
  } else if (speed < 0) {
    digitalWrite(in1, LOW);   digitalWrite(in2, HIGH);
    ledcWrite(pwmChannel, (uint8_t)(-speed));
  } else {
    digitalWrite(in1, LOW);   digitalWrite(in2, LOW);
    ledcWrite(pwmChannel, 0);
  }
}

void setLeftMotor(int speed)  {
  setMotor(PWM_CH_LM, PIN_LM_IN1, PIN_LM_IN2, INVERT_LEFT  ? -speed : speed);
}
void setRightMotor(int speed) {
  setMotor(PWM_CH_RM, PIN_RM_IN3, PIN_RM_IN4, INVERT_RIGHT ? -speed : speed);
}
void stopMotors() { setLeftMotor(0); setRightMotor(0); }


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                              SERVO                                   ║
// ╚══════════════════════════════════════════════════════════════════════╝

void setPen(bool down) {
  if (down == penIsDown) return;
  penServo.write(down ? PEN_DOWN_ANGLE : PEN_UP_ANGLE);
  penIsDown = down;
  Serial.printf("pen -> %s\n", down ? "DOWN" : "UP");
}


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                     UDP COMMAND HANDLING                             ║
// ╚══════════════════════════════════════════════════════════════════════╝

void handleCommand(char* json) {
  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, json);
  if (err) {
    Serial.printf("Bad JSON: %s\n", err.c_str());
    return;
  }

  int left  = doc["left"]  | 0;
  int right = doc["right"] | 0;
  int pen   = doc["pen"]   | 0;

  setLeftMotor(left);
  setRightMotor(right);
  setPen(pen != 0);
}


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                  TFT — KATHAKALI EYES                                ║
// ╚══════════════════════════════════════════════════════════════════════╝
//
//   The look: two large almond eyes on a white background. Black kohl
//   outline, white sclera, small black pupil that slowly glances side
//   to side, with an occasional quick dart and a slow blink every few
//   seconds. Status dot in the top-right shows WiFi state.
//
//   The shape uses stacked ellipses (outer black, inner white) — close
//   enough to a real Kathakali "Pacha" eye at this resolution, and fast
//   enough to animate smoothly on the ESP32.

void drawKathakaliEyes(float pupilOffsetX, float heightScale) {
  drawEye(LEFT_EYE_X,  EYE_Y, pupilOffsetX, heightScale);
  drawEye(RIGHT_EYE_X, EYE_Y, pupilOffsetX, heightScale);

  // Status dot — green if connected, red if not
  bool connected = (WiFi.status() == WL_CONNECTED);
  tft.fillCircle(SCREEN_W - 7, 7, 4, connected ? TFT_GREEN : TFT_RED);
}


void drawEye(int cx, int cy, float pupilOffsetX, float heightScale) {
  int w = EYE_W;
  int h = max(2, (int)(EYE_H * heightScale));

  // Clear the eye region with a small pad to kill edge artifacts
  int pad = 6;
  tft.fillRect(cx - w/2 - pad, cy - EYE_H/2 - pad,
               w + 2*pad, EYE_H + 2*pad, TFT_WHITE);

  // Fully closed → just a thin line (the lid)
  if (heightScale < 0.05f) {
    tft.drawFastHLine(cx - w/2, cy, w, TFT_BLACK);
    return;
  }

  // Outer black almond (the iconic kohl outline)
  tft.fillEllipse(cx, cy, w/2,         h/2,         TFT_BLACK);
  // Inner white sclera — 2 px inset gives a clean 2 px kohl border
  tft.fillEllipse(cx, cy, w/2 - 2,     h/2 - 2,     TFT_WHITE);

  // Pupil — moves with the offset parameter
  int pupilX = cx + (int)pupilOffsetX;
  int pupilR = max(2, h / 6);
  tft.fillCircle(pupilX, cy, pupilR, TFT_BLACK);
}


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                         ANIMATION TICK                               ║
// ╚══════════════════════════════════════════════════════════════════════╝

void animateEyes() {
  unsigned long now = millis();
  float t = (now - bootMs) / 1000.0f;

  // Pupil: slow side-to-side glance + occasional quick dart
  float slow  = sinf(t * 1.4f) * 4.0f;                      // ±4 px, ~4.5 s period
  float quick = (sinf(t * 0.7f) > 0.95f) ? sinf(t * 8.0f) * 6.0f : 0.0f;
  eyePupilX = slow + quick;

  // Blink every 4–5 s (300 ms total — 150 close, 150 open)
  if (!inBlink && (now - lastBlinkStart > 4500 + (unsigned long)(t * 100.0f) % 1000)) {
    inBlink = true;
    lastBlinkStart = now;
  }
  if (inBlink) {
    unsigned long dt = now - lastBlinkStart;
    if (dt < 150) {
      eyeHeightScale = 1.0f - (dt / 150.0f);
    } else if (dt < 300) {
      eyeHeightScale = (dt - 150) / 150.0f;
    } else {
      eyeHeightScale = 1.0f;
      inBlink = false;
      lastBlinkStart = now;
    }
  } else {
    eyeHeightScale = 1.0f;
  }

  drawKathakaliEyes(eyePupilX, eyeHeightScale);
}


// ╔══════════════════════════════════════════════════════════════════════╗
// ║                              LOOP                                    ║
// ╚══════════════════════════════════════════════════════════════════════╝

unsigned long lastAnimateMs  = 0;
unsigned long lastWifiCheckMs = 0;
unsigned long lastHeartbeatMs = 0;
const unsigned long ANIMATE_INTERVAL_MS = 50;   // 20 Hz eye animation
const unsigned long WIFI_CHECK_MS       = 5000;
const unsigned long HEARTBEAT_MS        = 1000;

void loop() {
  unsigned long now = millis();

  // ── UDP receive ──────────────────────────────────────────────────────
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    int len = udp.read(packetBuf, sizeof(packetBuf) - 1);
    if (len > 0) {
      packetBuf[len] = 0;
      handleCommand(packetBuf);
      lastCommandMs = now;
    }
  }

  // ── Motor watchdog (safety) ─────────────────────────────────────────
  if (now - lastCommandMs > MOTOR_TIMEOUT_MS) {
    setLeftMotor(0);
    setRightMotor(0);
  }

  // ── WiFi reconnect ──────────────────────────────────────────────────
  if (now - lastWifiCheckMs > WIFI_CHECK_MS) {
    lastWifiCheckMs = now;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi down — reconnecting");
      WiFi.reconnect();
    }
  }

  // ── Heartbeat LED ───────────────────────────────────────────────────
  if (now - lastHeartbeatMs > HEARTBEAT_MS) {
    lastHeartbeatMs = now;
    // Toggle the on-board LED on GPIO 2 (most DevKits have it)
    digitalWrite(2, !digitalRead(2));
  }

  // ── Animate eyes at 20 Hz ───────────────────────────────────────────
  if (now - lastAnimateMs > ANIMATE_INTERVAL_MS) {
    lastAnimateMs = now;
    animateEyes();
  }
}
```

> **Tuning tips:**
> - The pupil's side-glance speed and amplitude are at the top of `animateEyes()` — change `sinf(t * 1.4f) * 4.0f` to taste.
> - The eye outline is `EYE_W=38` × `EYE_H=26` — make it smaller if your TFT is smaller.
> - `PEN_DOWN_ANGLE` and `PEN_UP_ANGLE` need to be measured by hand after you mount the pen (with the battery installed). Start at 0/90 and adjust until the pen just barely touches the floor when "down" and clears the floor when "up".
