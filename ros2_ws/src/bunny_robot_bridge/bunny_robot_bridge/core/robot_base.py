import time
from abc import ABC, abstractmethod
from typing import Dict, Iterator, Optional, Tuple, Union

from bunny_robot_bridge.core.models.telemetry import TelemetryFrame


class RobotBase(ABC):
    """Abstract base for robot implementations. Bridge uses this interface only."""

    @abstractmethod
    def move_forward(self) -> None:
        pass

    @abstractmethod
    def move_backward(self) -> None:
        pass

    @abstractmethod
    def move_left(self) -> None:
        pass

    @abstractmethod
    def move_right(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the robot by sending zero velocity commands."""
        pass

    def set_lamp(self, lamp: int) -> None:
        """
        Set lamp state (bitfield: 0=off, 1=front, 2=back, 3=both).
        Default no-op; subclasses that support lamps should override.
        """
        pass

    def send_velocity(self, linear: float, angular: float) -> None:
        """
        Send continuous velocity commands to the robot.
        linear: forward/backward speed (-1.0 to 1.0)
        angular: rotation speed left/right (-1.0 to 1.0)
        
        Default implementation converts to discrete commands for backward compatibility.
        Subclasses should override for smooth continuous control.
        """
        # Default: convert to discrete commands
        if abs(linear) > abs(angular):
            if linear > 0.1:
                self.move_forward()
            elif linear < -0.1:
                self.move_backward()
            else:
                self.stop()
        else:
            if angular > 0.1:
                self.move_right()
            elif angular < -0.1:
                self.move_left()
            else:
                self.stop()

    @abstractmethod
    def get_front_camera_frame(self) -> Optional[Union[bytes, Tuple[bytes, Dict[str, float]]]]:
        """Return latest front camera frame as raw bytes (or (bytes, metrics)), or None if unavailable."""
        pass

    def get_front_camera_stream(self, stop_event=None) -> Iterator[Optional[Union[bytes, Tuple[bytes, Dict[str, float]]]]]:
        """
        Yield front camera frames continuously at max sustainable rate.
        Caller can pass a threading.Event; when set, the iterator exits.
        """
        while stop_event is None or not stop_event.is_set():
            frame = self.get_front_camera_frame()
            yield frame
            time.sleep(0.01)

    @abstractmethod
    def get_telemetry(self) -> Optional[TelemetryFrame]:
        """
        Get latest telemetry data from the robot.
        
        Returns:
            TelemetryFrame containing sensor data, or None if unavailable.
        """
        pass
