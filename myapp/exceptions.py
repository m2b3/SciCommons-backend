"""
Centralized exception handling utilities.

This module provides safe error handling that prevents sensitive information
(database connection strings, internal paths, SQL queries, etc.) from being
exposed to API clients.
"""

import logging
from typing import Optional

from django.db import (
    DatabaseError,
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)

logger = logging.getLogger(__name__)


class SafeErrorMessages:
    """
    Safe, user-friendly error messages that don't expose sensitive information.

    These messages are intentionally generic to avoid revealing internal
    architecture details (database type, cache system, etc.) to clients.
    """

    # Authentication errors - these can be slightly specific since auth
    # is user-facing and helps users understand what action to take
    AUTH_GENERIC = "Authentication failed. Please try again."
    AUTH_TOKEN_INVALID = "Invalid or expired token. Please log in again."
    AUTH_TOKEN_EXPIRED = "Your session has expired. Please log in again."
    AUTH_USER_NOT_FOUND = "Unable to identify user. Please log in again."

    # Temporary service issues (503) - use for DB, cache, external service failures
    SERVICE_UNAVAILABLE = "Service temporarily unavailable. Please try again later."

    # Data conflict (409) - use for integrity errors, unique constraint violations
    DATA_CONFLICT = "A data conflict occurred. Please check your input and try again."

    # Resource errors
    RESOURCE_NOT_FOUND = "The requested resource was not found."

    # Generic errors (500) - use for unexpected/unclassified errors
    INTERNAL_ERROR = "An unexpected error occurred. Please try again later."

    # Validation errors (422/400)
    VALIDATION_ERROR = "Invalid input. Please check your data and try again."

    # Rate limiting (429)
    RATE_LIMITED = "Too many requests. Please try again later."


def classify_database_exception(exc: Exception) -> str:
    """
    Classify a database exception and return a safe error message.

    All database exceptions return generic messages to avoid revealing
    internal architecture details to clients.

    Args:
        exc: The exception to classify

    Returns:
        A safe, user-friendly error message
    """
    if isinstance(exc, IntegrityError):
        return SafeErrorMessages.DATA_CONFLICT

    if isinstance(exc, DataError):
        return SafeErrorMessages.VALIDATION_ERROR

    if isinstance(
        exc,
        (
            OperationalError,
            InterfaceError,
            ProgrammingError,
            NotSupportedError,
            InternalError,
            DatabaseError,
        ),
    ):
        return SafeErrorMessages.SERVICE_UNAVAILABLE

    return SafeErrorMessages.INTERNAL_ERROR


def is_database_exception(exc: Exception) -> bool:
    """
    Check if an exception is a database-related exception.

    Args:
        exc: The exception to check

    Returns:
        True if the exception is database-related, False otherwise
    """
    return isinstance(
        exc,
        (
            DatabaseError,
            OperationalError,
            InterfaceError,
            IntegrityError,
            DataError,
            ProgrammingError,
            NotSupportedError,
            InternalError,
        ),
    )


def get_safe_error_message(
    exc: Exception,
    context: Optional[str] = None,
    default_message: str = SafeErrorMessages.INTERNAL_ERROR,
) -> str:
    """
    Get a safe error message for any exception.

    This function ensures that no sensitive information is ever returned
    to the client, regardless of the exception type.

    Args:
        exc: The exception to get a message for
        context: Optional context to help classify the error (e.g., "authentication")
        default_message: Default message if no specific classification is found

    Returns:
        A safe, user-friendly error message
    """
    if is_database_exception(exc):
        return classify_database_exception(exc)

    if context == "authentication":
        return SafeErrorMessages.AUTH_GENERIC

    return default_message


def log_exception(
    exc: Exception,
    context: str,
    logger_instance: Optional[logging.Logger] = None,
    level: int = logging.ERROR,
) -> None:
    """
    Log an exception with full details for debugging.

    This should be called before returning a safe error message to the client,
    ensuring that developers can still debug issues while clients only see
    safe messages.

    Args:
        exc: The exception to log
        context: Description of where the error occurred
        logger_instance: Optional logger to use (defaults to module logger)
        level: Logging level (defaults to ERROR)
    """
    log = logger_instance or logger
    log.log(level, f"{context}: {type(exc).__name__}: {exc}", exc_info=True)
