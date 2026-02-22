"""Telemetry-aware teleop controller: velocity ramping and safety limits. No robot dependency."""

import logging
from typing import Optional

from connectx_controller.constants import (
    TELEOP_BATTERY_WARNING_THRESHOLD,
    TELEOP_BATTERY_SPEED_REDUCTION,
    TELEOP_GPS_WARNING_THRESHOLD,
    TELEOP_GPS_SPEED_REDUCTION,
    TELEOP_STUCK_VELOCITY_THRESHOLD,
    TELEOP_STUCK_RPM_THRESHOLD,
)
from connectx_controller.telemetry_safety import TelemetryForSafety


class TeleopController:
    """Velocity ramping and safety limits; telemetry passed in per tick."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        linear_max: float = 0.3,
        angular_max: float = 0.6,
        ramp_up_sec: float = 0.25,
        ramp_dn_sec: float = 0.15,
        decay_alpha: float = 0.85,
        control_hz: float = 50.0,
    ):
        self._logger = logger or logging.getLogger(__name__)
        self.linear_max = linear_max
        self.angular_max = angular_max
        self.ramp_up_sec = ramp_up_sec
        self.ramp_dn_sec = ramp_dn_sec
        self.decay_alpha = decay_alpha
        self.control_hz = control_hz

        self.cur_linear = 0.0
        self.cur_angular = 0.0
        self._linear_target = 0.0
        self._angular_target = 0.0

        self._linear_up_step = linear_max / (ramp_up_sec * control_hz)
        self._linear_dn_step = linear_max / (ramp_dn_sec * control_hz)
        self._angular_up_step = angular_max / (ramp_up_sec * control_hz)
        self._angular_dn_step = angular_max / (ramp_dn_sec * control_hz)

        self._last_telemetry: Optional[TelemetryForSafety] = None

    def set_target_velocities(self, linear_target: float, angular_target: float) -> None:
        self._linear_target = max(-self.linear_max, min(self.linear_max, linear_target))
        self._angular_target = max(-self.angular_max, min(self.angular_max, angular_target))

    def set_telemetry(self, telemetry: Optional[TelemetryForSafety]) -> None:
        self._last_telemetry = telemetry

    def tick(self, telemetry: Optional[TelemetryForSafety] = None) -> None:
        """
        Ramp toward targets and apply safety limits.

        Telemetry can be passed in or set via set_telemetry.
        """
        if telemetry is not None:
            self._last_telemetry = telemetry

        was_at_zero_linear = abs(self.cur_linear) < 0.01
        was_at_zero_angular = abs(self.cur_angular) < 0.01

        if abs(self._linear_target) > 0.001:
            if was_at_zero_linear:
                self.cur_linear = self._linear_target * 0.7
            else:
                self.cur_linear = self._ramp(
                    self.cur_linear,
                    self._linear_target,
                    self._linear_up_step,
                    self._linear_dn_step,
                )
        else:
            if abs(self.cur_linear) > 0.001:
                self.cur_linear = self._ramp(
                    self.cur_linear,
                    self._linear_target,
                    self._linear_up_step,
                    self._linear_dn_step,
                )
            else:
                self.cur_linear = 0.0

        if abs(self._angular_target) > 0.001:
            if was_at_zero_angular:
                self.cur_angular = self._angular_target * 0.7
            else:
                self.cur_angular = self._ramp(
                    self.cur_angular,
                    self._angular_target,
                    self._angular_up_step,
                    self._angular_dn_step,
                )
        else:
            if abs(self.cur_angular) > 0.001:
                self.cur_angular = self._ramp(
                    self.cur_angular,
                    self._angular_target,
                    self._angular_up_step,
                    self._angular_dn_step,
                )
            else:
                self.cur_angular = 0.0

        if abs(self._linear_target) < 0.001:
            if abs(self.cur_linear) > 0.001:
                self.cur_linear *= self.decay_alpha
                if abs(self.cur_linear) < 0.02:
                    self.cur_linear = 0.0
            else:
                self.cur_linear = 0.0

        if abs(self._angular_target) < 0.001:
            if abs(self.cur_angular) > 0.001:
                self.cur_angular *= self.decay_alpha
                if abs(self.cur_angular) < 0.02:
                    self.cur_angular = 0.0
            else:
                self.cur_angular = 0.0

        if self._last_telemetry:
            self.cur_linear = self._apply_safety_limits(self.cur_linear, self._last_telemetry)

    def _ramp(
        self, current: float, target: float, up_step: float, dn_step: float
    ) -> float:
        diff = target - current
        if abs(diff) < 1e-9:
            return target
        moving_toward_zero = (current * target <= 0) or (abs(target) < abs(current))
        step = dn_step if moving_toward_zero else up_step
        if abs(diff) <= step:
            return target
        return current + step * (1 if diff > 0 else -1)

    def _apply_safety_limits(self, linear: float, telemetry: TelemetryForSafety) -> float:
        result = linear
        if telemetry.battery < TELEOP_BATTERY_WARNING_THRESHOLD:
            result *= TELEOP_BATTERY_SPEED_REDUCTION
            self._logger.warning(
                "Low battery (%.1f%%): reducing speed by %.0f%%",
                telemetry.battery,
                (1.0 - TELEOP_BATTERY_SPEED_REDUCTION) * 100,
            )
        if telemetry.gps_signal < TELEOP_GPS_WARNING_THRESHOLD:
            result *= TELEOP_GPS_SPEED_REDUCTION
            self._logger.debug(
                "Weak GPS signal (%.1f): reducing speed",
                telemetry.gps_signal,
            )
        avg_rpm = telemetry.average_rpm()
        if (
            abs(linear) > TELEOP_STUCK_VELOCITY_THRESHOLD
            and avg_rpm is not None
            and avg_rpm < TELEOP_STUCK_RPM_THRESHOLD
        ):
            self._logger.warning(
                "Stuck condition: commanded velocity=%.2f, average RPM=%.2f < %.2f",
                linear,
                avg_rpm,
                TELEOP_STUCK_RPM_THRESHOLD,
            )
            result = 0.0
        return result

    def get_current_velocities(self) -> tuple[float, float]:
        return (self.cur_linear, self.cur_angular)

    def get_last_telemetry(self) -> Optional[TelemetryForSafety]:
        return self._last_telemetry
