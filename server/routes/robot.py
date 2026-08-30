"""
server/routes/robot.py — Robot Control, Teleop & Real Autonomous Closed-Loop Drawing Engine.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import control.calibration as calib_module
from control.controller import WaypointFollower
from control.localization import ArucoLocator, MouseOdometer, PoseFusion
from server.models import RobotSendRequest, RobotSendResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/robot", tags=["robot"])

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_ESP32_IP = os.environ.get("POOKALBOT_ESP32_IP", "192.168.11.237").strip()

_esp32_ip: str = DEFAULT_ESP32_IP
_tft_thread: Optional[threading.Thread] = None
_tft_stop_event = threading.Event()
_tft_streaming = False
_last_status: Optional[str] = "Idle"
_current_pen_down: bool = False
_motor_speed: int = 220

_draw_thread: Optional[threading.Thread] = None
_stop_draw_event = threading.Event()
_pause_draw_event = threading.Event()
_is_drawing = False


class ConnectRequest(BaseModel):
    esp32_ip: str
    stream_tft: bool = True


class TeleopRequest(BaseModel):
    action: str
    speed: Optional[int] = None


class ServoAngleRequest(BaseModel):
    angle: int


class DriveRequest(BaseModel):
    left: int = 0
    right: int = 0
    pen: Optional[int] = None


class TestDriveRequest(BaseModel):
    action: str = "forward"
    duration_sec: float = 0.5
    speed: int = 220


def _send_udp_packet(payload: str, ip: str = None, port: int = 9000):
    target_ip = ip or _esp32_ip
    data = payload.encode("utf-8")
    
    # 1. Direct UDP
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.sendto(data, (target_ip, port))
        sock.close()
    except Exception:
        pass

    # 2. Subnet broadcast
    try:
        parts = target_ip.split(".")
        if len(parts) == 4:
            bcast_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
            bsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            bsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            bsock.settimeout(0.2)
            bsock.sendto(data, (bcast_ip, port))
            bsock.close()
    except Exception:
        pass


def _tft_worker(ip: str):
    global _tft_streaming
    _tft_streaming = True
    
    from pi.stream_gif import stream, find_default_gif
    gif_path = find_default_gif(ROOT_DIR)
    
    log.info("Starting background TFT stream to %s:9001 (%s)", ip, gif_path.name)
    while not _tft_stop_event.is_set():
        try:
            stream(ip, gif_path, forced_fps=15, fit_mode="contain", port=9001)
        except Exception:
            if not _tft_stop_event.is_set():
                time.sleep(2)
    _tft_streaming = False


@router.post("/connect", summary="Connect to ESP32 Robot and launch TFT display stream")
def connect_robot(req: ConnectRequest):
    global _esp32_ip, _tft_thread, _tft_stop_event
    _esp32_ip = req.esp32_ip.strip()
    
    _send_udp_packet("STOP", _esp32_ip)

    if req.stream_tft:
        if _tft_thread is None or not _tft_thread.is_alive():
            _tft_stop_event.clear()
            _tft_thread = threading.Thread(target=_tft_worker, args=(_esp32_ip,), daemon=True)
            _tft_thread.start()

    return {
        "connected": True,
        "esp32_ip": _esp32_ip,
        "tft_streaming": _tft_streaming or req.stream_tft,
        "message": f"Connected to ESP32 at {_esp32_ip}",
    }


@router.post("/teleop", summary="Manual keyboard & joypad teleoperation")
def teleop(req: TeleopRequest):
    global _current_pen_down, _motor_speed
    act = req.action.lower().strip()
    spd = req.speed if req.speed is not None else _motor_speed
    _motor_speed = spd
    
    turn_spd = int(spd * 0.85)

    if act in ("up", "forward", "w"):
        _send_udp_packet(f"DRIVE:{spd},{spd}")
        return {"action": "forward", "left": spd, "right": spd}
        
    elif act in ("down", "back", "s"):
        _send_udp_packet(f"DRIVE:-{spd},-{spd}")
        return {"action": "back", "left": -spd, "right": -spd}
        
    elif act in ("left", "a"):
        _send_udp_packet(f"DRIVE:-{turn_spd},{turn_spd}")
        return {"action": "left", "left": -turn_spd, "right": turn_spd}
        
    elif act in ("right", "d"):
        _send_udp_packet(f"DRIVE:{turn_spd},-{turn_spd}")
        return {"action": "right", "left": turn_spd, "right": -turn_spd}
        
    elif act in ("stop", "release", "estop"):
        _send_udp_packet("STOP")
        return {"action": "stop", "left": 0, "right": 0}
        
    elif act in ("space", "pen_toggle"):
        _current_pen_down = not _current_pen_down
        cmd = "PEN:DOWN" if _current_pen_down else "PEN:UP"
        _send_udp_packet(cmd)
        return {"action": "pen_toggle", "pen_down": _current_pen_down}

    elif act == "pen_down":
        _current_pen_down = True
        _send_udp_packet("PEN:DOWN")
        return {"action": "pen_down", "pen_down": True}

    elif act == "pen_up":
        _current_pen_down = False
        _send_udp_packet("PEN:UP")
        return {"action": "pen_up", "pen_down": False}
        
    return {"action": act, "status": "unknown"}


@router.post("/servo_angle", summary="Set custom servo angle")
def set_servo_angle(req: ServoAngleRequest):
    angle = max(0, min(180, req.angle))
    _send_udp_packet(f"SERVO:{angle}")
    return {"ok": True, "angle": angle}


@router.post("/drive", summary="Direct speed control")
def drive(req: DriveRequest):
    pen_str = f', "pen": {req.pen}' if req.pen is not None else ""
    json_cmd = f'{{"left": {req.left}, "right": {req.right}{pen_str}}}'
    _send_udp_packet(json_cmd)
    return {"left": req.left, "right": req.right, "pen": req.pen}


@router.post("/test_drive", summary="Test motor movement")
def test_drive(req: TestDriveRequest):
    spd = req.speed
    turn_spd = int(spd * 0.85)
    cmd_map = {
        "forward": f"DRIVE:{spd},{spd}",
        "back":    f"DRIVE:-{spd},-{spd}",
        "left":    f"DRIVE:-{turn_spd},{turn_spd}",
        "right":   f"DRIVE:{turn_spd},-{turn_spd}",
        "spin":    f"DRIVE:{turn_spd},-{turn_spd}",
        "stop":    "STOP",
    }
    cmd = cmd_map.get(req.action.lower(), "STOP")
    _send_udp_packet(cmd)
    
    if req.action.lower() != "stop" and req.duration_sec > 0:
        def _stop_later():
            time.sleep(req.duration_sec)
            _send_udp_packet("STOP")
        threading.Thread(target=_stop_later, daemon=True).start()

    return {"ok": True, "action": req.action, "sent_cmd": cmd, "target_ip": _esp32_ip}


# ── Autonomous Closed-Loop Path Execution ────────────────────────────────────

def _autonomous_draw_worker(waypoints: List[dict]):
    """Real closed-loop control loop running at 10 Hz."""
    global _is_drawing, _last_status
    _is_drawing = True
    _last_status = "Autonomous Drawing Active"

    from server.routes.camera import CameraManager
    from server.routes.live import _state

    cam_mgr = CameraManager.get_instance()
    locator = ArucoLocator()
    odometer = MouseOdometer()
    fusion = PoseFusion()
    follower = WaypointFollower(waypoints)

    total_wps = len(waypoints)
    _state.progress.state = "drawing"
    _state.progress.drawing = True
    _state.progress.total_waypoints = total_wps
    _state.progress.current_waypoint = 0

    log.info("Started real autonomous closed-loop drawing for %d waypoints...", total_wps)

    try:
        while not follower.done and not _stop_draw_event.is_set():
            if _pause_draw_event.is_set():
                _send_udp_packet("STOP")
                time.sleep(0.2)
                continue

            loop_start = time.time()

            # 1. Camera ArUco pose
            frame = cam_mgr.get_latest_frame()
            det = locator.detect(frame) if frame is not None else None
            cam_pose = (det[0], det[1], det[2]) if det else None

            # 2. Mouse odometry & fusion
            dx_cm, dy_cm = odometer.poll_cm()
            pose = fusion.update(cam_pose, dx_cm, dy_cm)

            # 3. Path following control step
            left, right, pen = follower.step(pose)

            # 4. Transmit to ESP32
            drive_cmd = f'{{"left": {left}, "right": {right}, "pen": {pen}}}'
            _send_udp_packet(drive_cmd)
            _send_udp_packet(f"DRIVE:{left},{right}")
            _send_udp_packet("PEN:DOWN" if pen else "PEN:UP")

            # 5. Update live telemetry
            cur_idx = follower.index
            _state.progress.current_waypoint = cur_idx
            _state.progress.eta_seconds = int((total_wps - cur_idx) * 0.25)
            _state.pen = "down" if pen else "up"
            _state.robot.x = pose[0]
            _state.robot.y = pose[1]
            _state.robot.theta = pose[2]
            _state.robot.detected = (cam_pose is not None)
            _state.message = f"Drawing waypoint {cur_idx}/{total_wps} (Pen: {'DOWN' if pen else 'UP'})"

            elapsed = time.time() - loop_start
            time.sleep(max(0.01, 0.10 - elapsed))

    finally:
        _send_udp_packet("STOP")
        _send_udp_packet("PEN:UP")
        _is_drawing = False
        _state.progress.drawing = False
        _state.pen = "up"
        if _stop_draw_event.is_set():
            _state.progress.state = "idle"
            _state.message = "Drawing stopped."
        else:
            _state.progress.state = "done"
            _state.message = "🎉 Drawing completed successfully!"


@router.post("/send", response_model=RobotSendResponse, summary="Send full waypoint path to robot and begin drawing")
async def send_to_robot(req: RobotSendRequest) -> RobotSendResponse:
    global _draw_thread, _stop_draw_event, _pause_draw_event
    n = len(req.waypoints)
    if n == 0:
        raise HTTPException(status_code=400, detail="Waypoint list is empty.")

    _stop_draw_event.clear()
    _pause_draw_event.clear()

    # Pass waypoints to closed-loop execution thread
    wps = [w.model_dump() for w in req.waypoints]
    _draw_thread = threading.Thread(target=_autonomous_draw_worker, args=(wps,), daemon=True)
    _draw_thread.start()

    return RobotSendResponse(
        accepted=True,
        design_id=req.design_id,
        message=f"✓ Autonomous drawing launched! ({n} waypoints). Tracking robot pose at {_esp32_ip}.",
        control_service_status="drawing",
    )


@router.post("/stop_job", summary="Emergency Stop active drawing job")
def stop_job():
    global _stop_draw_event
    _stop_draw_event.set()
    _send_udp_packet("STOP")
    _send_udp_packet("PEN:UP")
    return {"ok": True, "message": "Autonomous drawing stopped."}


@router.post("/pause_job", summary="Pause / Resume drawing job")
def pause_job(pause: bool = True):
    global _pause_draw_event
    if pause:
        _pause_draw_event.set()
        _send_udp_packet("STOP")
    else:
        _pause_draw_event.clear()
    return {"ok": True, "paused": pause}


@router.get("/status", summary="Robot and display status")
def robot_status():
    return {
        "esp32_ip": _esp32_ip,
        "tft_streaming": _tft_streaming,
        "is_drawing": _is_drawing,
        "pen_down": _current_pen_down,
        "motor_speed": _motor_speed,
        "status": _last_status,
    }
