"""
test_protocol.py — bench test for PookalBot serial round-trip

Sends a turret_move command and prints the next status response.
Run with: python test_protocol.py [port]

Default port: /dev/ttyUSB0  (pass COM3 etc. as first arg on Windows)
"""

import sys
import time
import logging
from serial_link import SerialLink

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

TURRET_MOVE_CMD = {
    "cmd":   "turret_move",
    "theta": 1.5708,   # ~90° in radians
    "r":     120.0,    # 120 mm from center
}

def main():
    link = SerialLink(PORT)
    link.connect()

    # Give the ESP32 a moment to boot / send its first status
    time.sleep(0.5)

    print(f"\n→ Sending command: {TURRET_MOVE_CMD}")
    link.send_command(TURRET_MOVE_CMD)

    # Wait up to 1 second for the next status packet (~200 ms cadence)
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if link.last_status is not None:
            s = link.last_status
            print("\n← Status received:")
            print(f"   status       : {s.status}")
            print(f"   phase        : {s.phase}")
            print(f"   turret_theta : {s.turret_theta}")
            print(f"   turret_r     : {s.turret_r}")
            print(f"   battery_mv   : {s.battery_mv}")
            print(f"   obstacle     : {s.obstacle}")
            break
        time.sleep(0.05)
    else:
        print("\n✗ No status received within 1 s — check wiring and port.")

    link.disconnect()

if __name__ == "__main__":
    main()
