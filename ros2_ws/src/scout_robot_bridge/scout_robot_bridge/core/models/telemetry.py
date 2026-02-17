"""Telemetry data models for robot sensor data."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TelemetryFrame:
    """Telemetry frame containing sensor data from the robot.
    
    This dataclass represents the complete telemetry payload from the robot's
    /data endpoint, including IMU data, GPS, wheel speeds, and robot state.
    
    Attributes:
        battery: Battery level (0-100)
        signal_level: Signal strength level (0-5)
        speed: Current speed of the robot
        lamp: Lamp state (0=off, 1=on)
        latitude: GPS latitude in degrees
        longitude: GPS longitude in degrees
        gps_signal: GPS signal quality/strength
        orientation: Compass heading (0-255, maps to 0-360 degrees)
        vibration: Vibration level (optional)
        accels: List of accelerometer samples, each [x, y, z, timestamp]
                Units: m/s², gravity-referenced
        gyros: List of gyroscope samples, each [x, y, z, timestamp]
               Units: rad/s angular velocity
        mags: List of magnetometer samples, each [x, y, z, timestamp]
              Units: µT (microteslas)
        rpms: List of wheel RPM samples, each [fl, fr, rl, rr, timestamp]
              Units: RPM for front-left, front-right, rear-left, rear-right wheels
        timestamp: Timestamp of the telemetry frame (Unix epoch)
    """
    
    # Core state
    battery: float
    signal_level: int
    speed: float
    lamp: int
    
    # GPS
    latitude: float
    longitude: float
    gps_signal: float
    
    # Orientation (compass heading 0-255)
    orientation: int
    
    # IMU - each sample is [x, y, z, timestamp]
    accels: List[List[float]]  # m/s², gravity-referenced
    gyros: List[List[float]]    # rad/s angular velocity
    mags: List[List[float]]     # magnetometer (µT)
    
    # Wheel RPMs - [fl, fr, rl, rr, timestamp]
    rpms: List[List[float]]
    
    # Timestamp
    timestamp: float
    
    # Optional vibration field
    vibration: Optional[float] = None
    
    def orientation_degrees(self) -> float:
        """Convert orientation (0-255) to degrees (0-360)."""
        return (self.orientation / 255.0) * 360.0
