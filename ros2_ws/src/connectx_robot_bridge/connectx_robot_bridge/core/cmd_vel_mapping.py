"""Command/velocity mapping: ROS Twist to SDK normalized range [-1, 1]."""

from connectx_robot_bridge.core.constants import MAX_VELOCITY, MIN_VELOCITY


def twist_to_sdk_normalized(
    linear_x: float,
    angular_z: float,
    max_linear: float,
    max_angular: float,
) -> tuple[float, float]:
    """
    Map ROS Twist (m/s, rad/s) to SDK range [-1.0, 1.0].

    Args
    ----
    linear_x : float
        Forward/backward velocity in m/s
    angular_z : float
        Rotation in rad/s
    max_linear : float
        Max linear speed (m/s) for scaling
    max_angular : float
        Max angular speed (rad/s) for scaling

    Returns
    -------
    tuple[float, float]
        (linear_normalized, angular_normalized) in [-1.0, 1.0]

    """
    linear_normalized = (
        max(MIN_VELOCITY, min(MAX_VELOCITY, linear_x / max_linear))
        if max_linear > 0
        else 0.0
    )
    angular_normalized = (
        max(MIN_VELOCITY, min(MAX_VELOCITY, angular_z / max_angular))
        if max_angular > 0
        else 0.0
    )
    return (linear_normalized, angular_normalized)
