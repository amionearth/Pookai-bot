"""
control/find_mouse.py — Helper to find Linux mouse event device path.
"""
import sys

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    print("evdev not installed. Run: pip install evdev")
    sys.exit(1)

print("Devices reporting relative motion (candidates for mouse sensor):\n")
candidates = []
for path in list_devices():
    try:
        dev = InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_REL, [])
        if ecodes.REL_X in caps and ecodes.REL_Y in caps:
            candidates.append(path)
            print(f"  {path}  —  {dev.name}")
    except Exception:
        pass

if not candidates:
    print("  (No relative motion devices found. Ensure USB mouse sensor is plugged in.)")
    sys.exit(1)

print(f"\nFound {len(candidates)} candidate(s). Set POOKALBOT_MOUSE_DEVICE={candidates[0]}")
