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
    def get_front_camera_frame(self) -> Optional[bytes]:
        """Return latest front camera frame as raw bytes, or None if unavailable."""
        pass
