"""
serial_link.py — PookalBot UART communication layer (Pi side)

Sends JSON commands to the ESP32 and receives status updates in the background.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

import serial

log = logging.getLogger(__name__)

BAUD_RATE    = 115200
READ_TIMEOUT = 1.0  # seconds


@dataclass
class StatusUpdate:
    status:       str   = "ok"
    phase:        str   = "idle"
    turret_theta: float = 0.0
    turret_r:     float = 0.0
    battery_mv:   int   = 0
    obstacle:     bool  = False


class SerialLink:
    def __init__(
        self,
        port: str,
        on_status: Optional[Callable[[StatusUpdate], None]] = None,
        baud: int = BAUD_RATE,
    ):
        """
        port      — e.g. '/dev/ttyUSB0' or 'COM3'
        on_status — optional callback called on every parsed status line
        """
        self._port      = port
        self._baud      = baud
        self._on_status = on_status
        self._ser:   Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.last_status: Optional[StatusUpdate] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._ser = serial.Serial(self._port, self._baud, timeout=READ_TIMEOUT)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        log.info("SerialLink connected on %s @ %d", self._port, self._baud)

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._ser and self._ser.is_open:
            self._ser.close()
        log.info("SerialLink disconnected")

    def send_command(self, cmd: dict) -> None:
        """Serialize cmd to JSON and write it as a single line over UART."""
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("SerialLink not connected")
        line = json.dumps(cmd, separators=(",", ":")) + "\n"
        self._ser.write(line.encode("utf-8"))
        log.debug("TX: %s", line.rstrip())

    # ── Background reader ─────────────────────────────────────────────────────

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                raw = self._ser.readline()
            except serial.SerialException as e:
                log.error("Serial read error: %s", e)
                break

            if not raw:
                continue  # timeout — loop again

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            log.debug("RX: %s", line)
            status = _parse_status(line)
            if status is None:
                continue  # malformed — already logged inside _parse_status

            self.last_status = status
            if self._on_status:
                try:
                    self._on_status(status)
                except Exception as e:
                    log.error("on_status callback raised: %s", e)


def _parse_status(line: str) -> Optional[StatusUpdate]:
    try:
        data = json.loads(line)
        return StatusUpdate(
            status       = data.get("status", "ok"),
            phase        = data.get("phase", ""),
            turret_theta = float(data.get("turret_theta", 0.0)),
            turret_r     = float(data.get("turret_r", 0.0)),
            battery_mv   = int(data.get("battery_mv", 0)),
            obstacle     = bool(data.get("obstacle", False)),
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log.warning("Malformed status line (skipping): %s | error: %s", line, e)
        return None
