"""Telemetry-aware teleop controller with velocity ramping and safety limits."""

import logging
from typing import Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from scout_robot_bridge.core.constants import (
    TELEOP_BATTERY_WARNING_THRESHOLD,
    TELEOP_BATTERY_SPEED_REDUCTION,
    TELEOP_GPS_WARNING_THRESHOLD,
    TELEOP_GPS_SPEED_REDUCTION,
    TELEOP_STUCK_VELOCITY_THRESHOLD,
    TELEOP_STUCK_RPM_THRESHOLD,
)
from scout_robot_bridge.core.models.telemetry import TelemetryFrame
from scout_robot_bridge.core.robot_base import RobotBase


class TeleopController:
    """Telemetry-aware teleop controller with velocity ramping and safety limits."""

    def __init__(
        self,
        robot: RobotBase,
        logger: Optional[logging.Logger] = None,
        linear_max: float = 0.3,
        angular_max: float = 0.6,
        ramp_up_sec: float = 0.25,
        ramp_dn_sec: float = 0.15,
        decay_alpha: float = 0.85,
        control_hz: float = 50.0,
    ):
        """
        Initialize teleop controller.

        Args:
            robot: Robot instance to control
            logger: Optional logger instance
            linear_max: Maximum linear velocity (m/s)
            angular_max: Maximum angular velocity (rad/s)
            ramp_up_sec: Seconds to reach full speed from zero
            ramp_dn_sec: Seconds to reach zero from full speed
            decay_alpha: Exponential decay multiplier when no key held (0-1)
            control_hz: Control loop frequency (Hz)
        """
        self.robot = robot
        self._logger = logger or logging.getLogger(__name__)

        # Velocity limits
        self.linear_max = linear_max
        self.angular_max = angular_max

        # Ramp parameters
        self.ramp_up_sec = ramp_up_sec
        self.ramp_dn_sec = ramp_dn_sec
        self.decay_alpha = decay_alpha
        self.control_hz = control_hz

        # Current output velocities
        self.cur_linear = 0.0
        self.cur_angular = 0.0

        # Target velocities (set by external code)
        self._linear_target = 0.0
        self._angular_target = 0.0

        # Per-tick ramp increments
        dt = 1.0 / control_hz
        self._linear_up_step = linear_max / (ramp_up_sec * control_hz)
        self._linear_dn_step = linear_max / (ramp_dn_sec * control_hz)
        self._angular_up_step = angular_max / (ramp_up_sec * control_hz)
        self._angular_dn_step = angular_max / (ramp_dn_sec * control_hz)
        
        # Initial velocity kick for instant response (70% of max - immediately noticeable)
        self._initial_kick_linear = linear_max * 0.7
        self._initial_kick_angular = angular_max * 0.7

        # Track last telemetry for stuck detection
        self._last_telemetry: Optional[TelemetryFrame] = None

    def set_target_velocities(self, linear_target: float, angular_target: float) -> None:
        """
        Set target velocities from keyboard input.

        Args:
            linear_target: Target linear velocity (-linear_max to linear_max)
            angular_target: Target angular velocity (-angular_max to angular_max)
        """
        self._linear_target = max(-self.linear_max, min(self.linear_max, linear_target))
        self._angular_target = max(-self.angular_max, min(self.angular_max, angular_target))

    def tick(self) -> None:
        """
        Main control loop tick. Call at control_hz frequency.

        Ramps velocities toward targets, applies safety limits based on telemetry,
        and sends velocity commands to robot.
        """
        # Instant response: if target changed from zero, give it a kick start
        # Check if we're starting from zero (or very close to it)
        was_at_zero_linear = abs(self.cur_linear) < 0.01
        was_at_zero_angular = abs(self.cur_angular) < 0.01
        
        if abs(self._linear_target) > 0.001:
            if was_at_zero_linear:
                # Starting from zero - give instant kick to 70% of target
                self.cur_linear = self._linear_target * 0.7
            else:
                # Already moving - ramp toward target
                self.cur_linear = self._ramp(
                    self.cur_linear,
                    self._linear_target,
                    self._linear_up_step,
                    self._linear_dn_step,
                )
        else:
            # Target is zero - ramp down, but skip if already at zero
            if abs(self.cur_linear) > 0.001:
                self.cur_linear = self._ramp(
                    self.cur_linear,
                    self._linear_target,
                    self._linear_up_step,
                    self._linear_dn_step,
                )
            else:
                # Already at zero - keep it at zero
                self.cur_linear = 0.0

        # Instant response: if target changed from zero, give it a kick start
        if abs(self._angular_target) > 0.001:
            if was_at_zero_angular:
                # Starting from zero - give instant kick to 70% of target
                self.cur_angular = self._angular_target * 0.7
            else:
                # Already moving - ramp toward target
                self.cur_angular = self._ramp(
                    self.cur_angular,
                    self._angular_target,
                    self._angular_up_step,
                    self._angular_dn_step,
                )
        else:
            # Target is zero - ramp down, but skip if already at zero
            if abs(self.cur_angular) > 0.001:
                self.cur_angular = self._ramp(
                    self.cur_angular,
                    self._angular_target,
                    self._angular_up_step,
                    self._angular_dn_step,
                )
            else:
                # Already at zero - keep it at zero
                self.cur_angular = 0.0

        # Apply exponential decay when no keys held, but skip if already at zero
        if abs(self._linear_target) < 0.001:
            if abs(self.cur_linear) > 0.001:
                self.cur_linear *= self.decay_alpha
                # Snap to zero if below threshold to prevent infinite coast
                if abs(self.cur_linear) < 0.02:
                    self.cur_linear = 0.0
            else:
                # Already at zero - keep it at zero
                self.cur_linear = 0.0

        if abs(self._angular_target) < 0.001:
            if abs(self.cur_angular) > 0.001:
                self.cur_angular *= self.decay_alpha
                # Snap to zero if below threshold to prevent infinite coast
                if abs(self.cur_angular) < 0.02:
                    self.cur_angular = 0.0
            else:
                # Already at zero - keep it at zero
                self.cur_angular = 0.0

        # Fetch telemetry and apply safety limits
        telemetry = self.robot.get_telemetry()
        if telemetry:
            self.cur_linear = self._apply_safety_limits(self.cur_linear, telemetry)
            self._last_telemetry = telemetry

        # Send velocity command directly to robot
        # Convert from m/s and rad/s to robot's normalized [-1.0, 1.0] range
        linear_normalized = self.cur_linear / self.linear_max if self.linear_max > 0 else 0.0
        angular_normalized = self.cur_angular / self.angular_max if self.angular_max > 0 else 0.0

        # Clamp to valid range
        linear_normalized = max(-1.0, min(1.0, linear_normalized))
        angular_normalized = max(-1.0, min(1.0, angular_normalized))

        # Send velocity command to robot
        self._logger.debug(f"Sending velocity to robot: linear={linear_normalized:.3f}, angular={angular_normalized:.3f}")
        self.robot.send_velocity(linear_normalized, angular_normalized)

    def _ramp(
        self, current: float, target: float, up_step: float, dn_step: float
    ) -> float:
        """
        Ramp current velocity toward target.

        Args:
            current: Current velocity
            target: Target velocity
            up_step: Step size when accelerating
            dn_step: Step size when decelerating

        Returns:
            New velocity after ramping
        """
        diff = target - current
        if abs(diff) < 1e-9:
            return target

        # Determine if moving toward zero (decelerating)
        moving_toward_zero = (current * target <= 0) or (abs(target) < abs(current))
        step = dn_step if moving_toward_zero else up_step

        if abs(diff) <= step:
            return target

        return current + step * (1 if diff > 0 else -1)

    def _apply_safety_limits(self, linear: float, telemetry: TelemetryFrame) -> float:
        """
        Apply safety limits based on telemetry data.

        Args:
            linear: Current linear velocity command
            telemetry: Current telemetry frame

        Returns:
            Adjusted linear velocity after applying safety limits
        """
        result = linear

        # Battery check: reduce speed on low battery
        if telemetry.battery < TELEOP_BATTERY_WARNING_THRESHOLD:
            result *= TELEOP_BATTERY_SPEED_REDUCTION
            self._logger.warning(
                f"Low battery ({telemetry.battery:.1f}%): reducing speed by "
                f"{1.0 - TELEOP_BATTERY_SPEED_REDUCTION:.0%}"
            )

        # GPS signal check: reduce speed when GPS signal is weak
        if telemetry.gps_signal < TELEOP_GPS_WARNING_THRESHOLD:
            result *= TELEOP_GPS_SPEED_REDUCTION
            self._logger.debug(
                f"Weak GPS signal ({telemetry.gps_signal:.1f}): reducing speed by "
                f"{1.0 - TELEOP_GPS_SPEED_REDUCTION:.0%}"
            )

        # Stuck detection: check if commanding motion but wheels aren't responding
        if abs(linear) > TELEOP_STUCK_VELOCITY_THRESHOLD and telemetry.rpms:
            # Calculate average RPM across all wheels
            try:
                rpm_values = [
                    abs(rpm[0]) + abs(rpm[1]) + abs(rpm[2]) + abs(rpm[3])
                    for rpm in telemetry.rpms
                    if len(rpm) >= 4
                ]
                if rpm_values:
                    if HAS_NUMPY:
                        avg_rpm = np.mean(rpm_values)
                    else:
                        avg_rpm = sum(rpm_values) / len(rpm_values)
                    if avg_rpm < TELEOP_STUCK_RPM_THRESHOLD:
                        self._logger.warning(
                            f"Stuck condition detected: commanded velocity={linear:.2f}, "
                            f"but average RPM={avg_rpm:.2f} < {TELEOP_STUCK_RPM_THRESHOLD}"
                        )
                        result = 0.0  # Cut power completely
            except (IndexError, ValueError) as e:
                self._logger.debug(f"Error calculating RPM average: {e}")

        return result

    def get_current_velocities(self) -> tuple[float, float]:
        """
        Get current velocity commands.

        Returns:
            Tuple of (linear, angular) velocities
        """
        return (self.cur_linear, self.cur_angular)

    def get_last_telemetry(self) -> Optional[TelemetryFrame]:
        """
        Get last telemetry frame.

        Returns:
            Last telemetry frame, or None if not available
        """
        return self._last_telemetry
