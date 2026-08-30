"""
control/esp32_link.py — Dual UDP link to ESP32 (Direct + Subnet Broadcast).
"""
import json
import socket

from . import config


class Esp32Link:
    def __init__(self, ip=None, port=None):
        self.ip = ip or config.ESP32_IP
        self.port = port or config.ESP32_PORT
        self.addr = (self.ip, self.port)
        
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send(self, left, right, pen):
        # 1. Send JSON command
        packet = json.dumps({"left": int(left), "right": int(right), "pen": int(pen)}).encode("utf-8")
        try:
            self._sock.sendto(packet, self.addr)
        except Exception:
            pass

        # 2. Also send text format: DRIVE:L,R and PEN:UP/DOWN
        try:
            drive_txt = f"DRIVE:{int(left)},{int(right)}".encode("utf-8")
            self._sock.sendto(drive_txt, self.addr)
            pen_txt = b"PEN:DOWN" if pen else b"PEN:UP"
            self._sock.sendto(pen_txt, self.addr)
        except Exception:
            pass

    def stop(self):
        try:
            self._sock.sendto(b"STOP", self.addr)
            packet = json.dumps({"left": 0, "right": 0, "pen": 0}).encode("utf-8")
            self._sock.sendto(packet, self.addr)
        except Exception:
            pass

    def close(self):
        self.stop()
        try:
            self._sock.close()
        except Exception:
            pass
