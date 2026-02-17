from abc import ABC, abstractmethod
from typing import Optional


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
    def get_front_camera_frame(self) -> Optional[bytes]:
        """Return latest front camera frame as raw bytes, or None if unavailable."""
        pass
