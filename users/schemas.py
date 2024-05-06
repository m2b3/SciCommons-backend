"""
This module defines the input and output schemas for user authentication actions.
It includes schemas for signing up, logging in, and requesting a password reset.
"""

from ninja import Schema


class SignUpSchemaIn(Schema):
    """
    Input schema for user sign up. Requires username, first and last name,
    email, password, and password confirmation.
    """

    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class SignUpSchemaOut(Schema):
    """
    Output schema for user sign up responses. Indicates the status of the
    registration attempt and provides a corresponding message.
    """

    status: str
    message: str


class LogInSchemaIn(Schema):
    """
    Input schema for user log in. Requires a login identifier (could be
    username or email) and a password.
    """

    login: str
    password: str


class ResetRequestSchema(Schema):
    """
    Schema for requesting a password reset. Requires the user's email address.
    """

    email: str
