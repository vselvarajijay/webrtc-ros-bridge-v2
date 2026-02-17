from typing import Optional

from scout_robot_bridge.robot_base import RobotBase
from scout_robot_bridge.robots.earth_rovers_robot import EarthRoversRobot


def create_robot(robot_type: str) -> Optional[RobotBase]:
    """Create a robot implementation for the given type. No ROS dependency."""
    if robot_type == "earth_rovers_sdk":
        return EarthRoversRobot()
    return None
