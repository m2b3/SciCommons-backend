from enum import Enum
from urllib.parse import quote_plus

COMMUNITY_TYPES = ["public", "private", "hidden"]
# class COMMUNITY_TYPES(str, Enum):
#     PUBLIC = "public"
#     PRIVATE = "private"
#     HIDDEN = "hidden"

COMMUNITY_TYPES_LIST = [e for e in COMMUNITY_TYPES]


class COMMUNITY_SETTINGS(str, Enum):
    ANYONE_CAN_JOIN = "anyone_can_join"
    INVITE_ONLY = "invite_only"
    REQUEST_TO_JOIN = "request_to_join"


# CACHE
ONE_MINUTE = 60
FIVE_MINUTES = 300
TEN_MINUTES = 600
FIFTEEN_MINUTES = 900
THIRTY_MINUTES = 1800
SIXTY_MINUTES = 3600
