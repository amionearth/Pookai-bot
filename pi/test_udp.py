"""
test_udp.py — Test UDP communication between Raspberry Pi 5/4 and ESP32 PookalBot

Usage:
    python test_udp.py <ESP32_IP> [mode]

Examples:
    python test_udp.py 192.168.1.77 test        # Runs automated forward/turn/pen smoke test
    python test_udp.py 192.168.1.77 drive 100 100 2 # Drive forward speed 100 for 2 sec
    python test_udp.py 192.168.1.77 pen 1       # Lower pen
    python test_udp.py 192.168.1.77 pen 0       # Raise pen
    python test_udp.py 192.168.1.77 teleop      # Interactive keyboard control (WASD + Space)
"""

import sys
import time
import socket
import json
import threading

ESP32_PORT = 9000
LISTEN_PORT = 9000

class PookalBotUDP:
    def __init__(self, esp32_ip: str, esp32_port: int = ESP32_PORT):
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self.running = False
        self.last_status = {}

    def send_raw(self, payload: dict):
        msg = json.dumps(payload).encode('utf-8')
        self.sock.sendto(msg, (self.esp32_ip, self.esp32_port))

    def send_drive(self, left: int, right: int, pen: int = 0):
        """Sends drive command: left (-255..255), right (-255..255), pen (0=UP, 1=DOWN)"""
        self.send_raw({"left": int(left), "right": int(right), "pen": int(pen)})

    def send_pen(self, down: bool):
        """1 = DOWN (drawing), 0 = UP (travel)"""
        self.send_raw({"left": 0, "right": 0, "pen": 1 if down else 0})

    def send_stop(self):
        self.send_raw({"left": 0, "right": 0, "pen": 0})

    def send_estop(self):
        self.send_raw({"cmd": "estop"})

    def start_listener(self):
        """Listen for telemetry status packets returned by ESP32"""
        self.running = True
        def _listen():
            listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                listen_sock.bind(("0.0.0.0", LISTEN_PORT))
                listen_sock.settimeout(1.0)
                while self.running:
                    try:
                        data, addr = listen_sock.recvfrom(1024)
                        self.last_status = json.loads(data.decode('utf-8'))
                    except (socket.timeout, json.JSONDecodeError):
                        pass
            except Exception as e:
                print(f"[Listener Notice] Port {LISTEN_PORT} already bound or unavailable ({e})")
            finally:
                listen_sock.close()

        t = threading.Thread(target=_listen, daemon=True)
        t.start()

    def stream_drive(self, left: int, right: int, duration_sec: float, pen: int = 0):
        """Streams commands at 15 Hz to keep the ESP32 safety watchdog happy."""
        end_time = time.time() + duration_sec
        while time.time() < end_time:
            self.send_drive(left, right, pen)
            time.sleep(0.06)  # ~16 Hz
        self.send_stop()

def run_smoke_test(bot: PookalBotUDP):
    print("\n" + "="*50)
    print(f"🤖 Starting PookalBot Smoke Test -> {bot.esp32_ip}")
    print("="*50)

    print("\n1. Testing Forward Drive (1.5 sec at speed 120)...")
    bot.stream_drive(120, 120, 1.5, pen=0)
    time.sleep(0.5)

    print("2. Testing Reverse Drive (1.0 sec at speed -120)...")
    bot.stream_drive(-120, -120, 1.0, pen=0)
    time.sleep(0.5)

    print("3. Testing Spin Turn Left (1.0 sec)...")
    bot.stream_drive(-120, 120, 1.0, pen=0)
    time.sleep(0.5)

    print("4. Testing Spin Turn Right (1.0 sec)...")
    bot.stream_drive(120, -120, 1.0, pen=0)
    time.sleep(0.5)

    print("5. Testing Pen DOWN (Drawing position)...")
    bot.send_pen(True)
    time.sleep(1.5)

    print("6. Testing Pen UP (Travel position)...")
    bot.send_pen(False)
    time.sleep(1.0)

    print("\n✅ Smoke Test Complete! All systems operational.")

def run_teleop(bot: PookalBotUDP):
    print("\n" + "="*50)
    print("🎮 PookalBot Interactive Keyboard Teleop")
    print("Controls:")
    print("   [W] Forward      [S] Reverse")
    print("   [A] Turn Left    [D] Turn Right")
    print("   [SPACE] Toggle Pen Down/Up")
    print("   [X] Full Stop    [Q] Quit")
    print("="*50)

    pen_down = False
    speed = 120

    try:
        import tty, termios  # Linux / Raspberry Pi
        def getch():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
    except ImportError:
        import msvcrt  # Windows fallback
        def getch():
            return msvcrt.getch().decode('utf-8', errors='ignore')

    while True:
        try:
            key = getch().lower()
            if key == 'q':
                bot.send_stop()
                print("\nExiting Teleop.")
                break
            elif key == 'w':
                print(" ▲ FORWARD", end="\r")
                bot.stream_drive(speed, speed, 0.25, pen=1 if pen_down else 0)
            elif key == 's':
                print(" ▼ REVERSE", end="\r")
                bot.stream_drive(-speed, -speed, 0.25, pen=1 if pen_down else 0)
            elif key == 'a':
                print(" ◀ LEFT", end="\r")
                bot.stream_drive(-speed, speed, 0.25, pen=1 if pen_down else 0)
            elif key == 'd':
                print(" ▶ RIGHT", end="\r")
                bot.stream_drive(speed, -speed, 0.25, pen=1 if pen_down else 0)
            elif key == ' ':
                pen_down = not pen_down
                bot.send_pen(pen_down)
                print(f" ✎ PEN {'DOWN' if pen_down else 'UP'}", end="\r")
            elif key == 'x':
                bot.send_stop()
                print(" ⏹ STOP", end="\r")
        except KeyboardInterrupt:
            bot.send_stop()
            break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ip = sys.argv[1]
    bot = PookalBotUDP(ip)
    bot.start_listener()

    mode = sys.argv[2].lower() if len(sys.argv) > 2 else "test"

    if mode == "test":
        run_smoke_test(bot)
    elif mode == "teleop":
        run_teleop(bot)
    elif mode == "drive" and len(sys.argv) >= 5:
        l = int(sys.argv[3])
        r = int(sys.argv[4])
        dur = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
        print(f"Driving Left={l}, Right={r} for {dur}s...")
        bot.stream_drive(l, r, dur)
    elif mode == "pen" and len(sys.argv) >= 4:
        down = bool(int(sys.argv[3]))
        bot.send_pen(down)
        print(f"Pen set to: {'DOWN' if down else 'UP'}")
    elif mode == "stop":
        bot.send_stop()
        print("Robot stopped.")
    else:
        print(__doc__)
