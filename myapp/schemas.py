"""
Common schema for all the models
"""

from ninja import Schema


class Tag(Schema):
    value: str
    label: str


# Generic Pagination schema
# The disadvantage of this approach is that proper response schema is not
# generated for the paginated response.


class Message(Schema):
    message: str
