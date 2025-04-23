from enum import Enum

COMMUNITY_TYPES  = ['public', 'private', 'hidden']
# class COMMUNITY_TYPES(str, Enum):
#     PUBLIC = "public"
#     PRIVATE = "private"
#     HIDDEN = "hidden"

COMMUNITY_TYPES_LIST = [e for e in COMMUNITY_TYPES]

class COMMUNITY_SETTINGS(str, Enum):
    ANYONE_CAN_JOIN = "anyone_can_join"
    INVITE_ONLY = "invite_only"
    REQUEST_TO_JOIN = "request_to_join"