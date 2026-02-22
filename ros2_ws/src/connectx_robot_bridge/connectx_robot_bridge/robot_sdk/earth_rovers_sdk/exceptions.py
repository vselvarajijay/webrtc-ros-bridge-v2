"""Local exceptions for Earth Rovers SDK when run standalone (e.g. in connectx_sdk container)."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required parameters."""

    pass
