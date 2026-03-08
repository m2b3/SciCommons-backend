"""
User configuration constants and default values.
"""

from enum import Enum
from typing import Any, Dict, TypedDict


class UserConfigKey(str, Enum):
    """
    Enum for user configuration keys.
    This is used in the OpenAPI schema for type safety.
    """

    ENABLE_EMAIL_NOTIFICATIONS = "enable_email_notifications"
    ENABLE_SOUND_ON_DISCUSSION_NOTIFICATION = "enable_sound_on_discussion_notification"


class UserConfigType(str, Enum):
    """
    Enum for configuration value types.
    """

    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"


class ConfigMetadata(TypedDict):
    """
    Metadata for a configuration setting.
    """

    default_value: Any
    config_type: UserConfigType


# Configuration metadata with default values and types
USER_CONFIG_METADATA: Dict[str, ConfigMetadata] = {
    UserConfigKey.ENABLE_EMAIL_NOTIFICATIONS: {
        "default_value": False,
        "config_type": UserConfigType.BOOLEAN,
    },
    UserConfigKey.ENABLE_SOUND_ON_DISCUSSION_NOTIFICATION: {
        "default_value": False,
        "config_type": UserConfigType.BOOLEAN,
    },
}


# Default values for each configuration (for backward compatibility)
USER_CONFIG_DEFAULTS: Dict[str, Any] = {
    key: metadata["default_value"] for key, metadata in USER_CONFIG_METADATA.items()
}


def get_default_value(config_key: str) -> Any:
    """
    Get the default value for a configuration key.

    Args:
        config_key: The configuration key

    Returns:
        The default value for the configuration key
    """
    return USER_CONFIG_DEFAULTS.get(config_key)


def get_config_type(config_key: str) -> UserConfigType | None:
    """
    Get the config type for a configuration key.

    Args:
        config_key: The configuration key

    Returns:
        The config type for the configuration key
    """
    metadata = USER_CONFIG_METADATA.get(config_key)
    return metadata["config_type"] if metadata else None


def get_config_metadata(config_key: str) -> ConfigMetadata | None:
    """
    Get the full metadata for a configuration key.

    Args:
        config_key: The configuration key

    Returns:
        The metadata for the configuration key
    """
    return USER_CONFIG_METADATA.get(config_key)


def get_all_default_configs() -> Dict[str, Any]:
    """
    Get all default configurations.

    Returns:
        Dictionary of all default configurations
    """
    return USER_CONFIG_DEFAULTS.copy()


def get_all_config_metadata() -> Dict[str, ConfigMetadata]:
    """
    Get all configuration metadata.

    Returns:
        Dictionary of all configuration metadata
    """
    return USER_CONFIG_METADATA.copy()


def validate_config_value(config_key: str, value: Any) -> tuple[bool, str | None]:
    """
    Validate that a value matches the expected type for a configuration key.

    Args:
        config_key: The configuration key
        value: The value to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    metadata = USER_CONFIG_METADATA.get(config_key)
    if not metadata:
        return False, f"Invalid configuration key: {config_key}"

    config_type = metadata["config_type"]

    # Validate based on config type
    if config_type == UserConfigType.BOOLEAN:
        if not isinstance(value, bool):
            return (
                False,
                f"Expected boolean value for {config_key}, got {type(value).__name__}",
            )
    elif config_type == UserConfigType.STRING:
        if not isinstance(value, str):
            return (
                False,
                f"Expected string value for {config_key}, got {type(value).__name__}",
            )
    elif config_type == UserConfigType.NUMBER:
        if not isinstance(value, (int, float)):
            return (
                False,
                f"Expected number value for {config_key}, got {type(value).__name__}",
            )

    return True, None
