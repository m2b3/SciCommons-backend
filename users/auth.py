import logging

from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from myapp.exceptions import (
    SafeErrorMessages,
    get_safe_error_message,
    is_database_exception,
    log_exception,
)

logger = logging.getLogger(__name__)


class JWTAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token):
        jwt_authentication = JWTAuthentication()
        try:
            validated_token = jwt_authentication.get_validated_token(token)
            user = jwt_authentication.get_user(validated_token)
            if user is None:
                raise HttpError(403, SafeErrorMessages.AUTH_USER_NOT_FOUND)
            return user
        except TokenError:
            raise HttpError(401, SafeErrorMessages.AUTH_TOKEN_INVALID)
        except InvalidToken:
            raise HttpError(401, SafeErrorMessages.AUTH_TOKEN_EXPIRED)
        except HttpError:
            raise
        except Exception as e:
            log_exception(e, "JWTAuth.authenticate", logger)
            if is_database_exception(e):
                raise HttpError(503, get_safe_error_message(e))
            raise HttpError(500, SafeErrorMessages.AUTH_GENERIC)


def OptionalJWTAuth(request: HttpRequest):
    """
    Function-based view to handle partially protected endpoints.
    Returns True if no token provided, otherwise validates and returns user.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return True
    if not auth_header.startswith("Bearer "):
        return True

    token = auth_header.split("Bearer ")[1]

    if token is None or token == "null":
        return True

    jwt_authentication = JWTAuthentication()
    try:
        validated_token = jwt_authentication.get_validated_token(token)
        user = jwt_authentication.get_user(validated_token)
        if user is None:
            raise HttpError(403, SafeErrorMessages.AUTH_USER_NOT_FOUND)
        request.auth = user
        return user
    except TokenError:
        raise HttpError(401, SafeErrorMessages.AUTH_TOKEN_INVALID)
    except InvalidToken:
        raise HttpError(401, SafeErrorMessages.AUTH_TOKEN_EXPIRED)
    except HttpError:
        raise
    except Exception as e:
        log_exception(e, "OptionalJWTAuth", logger)
        if is_database_exception(e):
            raise HttpError(503, get_safe_error_message(e))
        raise HttpError(500, SafeErrorMessages.AUTH_GENERIC)
