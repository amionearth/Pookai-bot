"""
control/calibrate_mouse.py — Helper to measure MOUSE_COUNTS_PER_CM.
"""
import argparse
import sys
import threading
import time

from . import config
from .localization import MouseOdometer, find_mouse_device

parser = argparse.ArgumentParser()
parser.add_argument("--distance-cm", type=float, default=100.0, help="Distance pushed in cm")
args = parser.parse_args()

device_path = config.MOUSE_DEVICE_PATH or find_mouse_device()
if not device_path:
    print("No mouse device found. Plug in optical mouse sensor and run find_mouse.py.")
    sys.exit(1)

odometer = MouseOdometer(device_path)
if not odometer.available:
    print(f"Couldn't open {device_path}. Try running with sudo.")
    sys.exit(1)

print(f"Push robot exactly {args.distance_cm} cm in a straight line.")
input("Press Enter to begin recording...")

total_dx_counts = 0.0
total_dy_counts = 0.0
start = time.time()
stop_flag = threading.Event()

def _wait_for_stop():
    input("Press Enter when you reach the target distance...\n")
    stop_flag.set()

threading.Thread(target=_wait_for_stop, daemon=True).start()

while not stop_flag.is_set():
    dx_cm, dy_cm = odometer.poll_cm()
    total_dx_counts += dx_cm * config.MOUSE_COUNTS_PER_CM
    total_dy_counts += dy_cm * config.MOUSE_COUNTS_PER_CM
    time.sleep(0.02)

total_counts = (total_dx_counts ** 2 + total_dy_counts ** 2) ** 0.5
elapsed = time.time() - start

if total_counts == 0:
    print("No motion detected. Check sensor position against floor.")
    sys.exit(1)

counts_per_cm = total_counts / args.distance_cm
print(f"\nMeasured {total_counts:.0f} counts over {elapsed:.1f}s.")
print(f"POOKALBOT_MOUSE_COUNTS_PER_CM = {counts_per_cm:.2f}")
