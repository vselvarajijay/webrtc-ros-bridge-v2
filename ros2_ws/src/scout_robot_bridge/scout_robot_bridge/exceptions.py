"""Custom exceptions for scout_robot_bridge."""


class ScoutRobotBridgeError(Exception):
    """Base exception for all scout_robot_bridge errors."""

    pass


class AuthenticationError(ScoutRobotBridgeError):
    """Raised when authentication fails or credentials are missing."""

    pass


class SDKConnectionError(ScoutRobotBridgeError):
    """Raised when the SDK is unreachable or connection fails."""

    pass


class RobotNotInitializedError(ScoutRobotBridgeError):
    """Raised when robot operations are attempted before initialization."""

    pass


class ConfigurationError(ScoutRobotBridgeError):
    """Raised when configuration is invalid or missing required parameters."""

    pass
