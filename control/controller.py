"""
control/controller.py — Waypoint following & steering control loop.
"""
import math

from . import config


class WaypointFollower:
    def __init__(self, waypoints):
        self.waypoints = list(waypoints)
        self.index = 0
        self.pen_down = False

    @property
    def done(self):
        return self.index >= len(self.waypoints)

    @property
    def progress(self):
        if not self.waypoints:
            return 1.0
        return min(1.0, self.index / len(self.waypoints))

    def step(self, pose):
        """pose: (x_cm, y_cm, heading_rad). Returns (left_pwm, right_pwm, pen_int)."""
        if self.done:
            return 0, 0, int(self.pen_down)

        x, y, heading = pose[:3]
        target = self.waypoints[self.index]
        tx, ty = target["x"], target["y"]
        target_pen = bool(target.get("pen", 0))

        dist = math.hypot(tx - x, ty - y)

        if dist <= config.WAYPOINT_REACHED_CM:
            self.index += 1
            if self.done:
                return 0, 0, int(self.pen_down)
            target = self.waypoints[self.index]
            tx, ty = target["x"], target["y"]
            target_pen = bool(target.get("pen", 0))
            dist = math.hypot(tx - x, ty - y)

        self.pen_down = target_pen

        desired_heading = math.atan2(ty - y, tx - x)
        heading_error = _wrap_angle(desired_heading - heading)

        # Large heading error -> turn in place
        if abs(heading_error) > math.radians(35):
            forward = 0.0
            turn = math.copysign(config.MIN_PWM_TO_MOVE + 30, heading_error)
            left = -turn
            right = turn
        else:
            forward = min(config.MAX_PWM, config.MIN_PWM_TO_MOVE + dist * 6.0)
            turn = config.HEADING_KP * heading_error
            left = forward - turn
            right = forward + turn

        left = _clamp_nonzero(left, config.MAX_PWM, config.MIN_PWM_TO_MOVE)
        right = _clamp_nonzero(right, config.MAX_PWM, config.MIN_PWM_TO_MOVE)

        return int(left), int(right), int(self.pen_down)


def _clamp_nonzero(v, max_pwm, min_pwm):
    if v > max_pwm:
        return max_pwm
    if v < -max_pwm:
        return -max_pwm
    if 0 < v < min_pwm:
        return min_pwm
    if -min_pwm < v < 0:
        return -min_pwm
    return v


def _wrap_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi
