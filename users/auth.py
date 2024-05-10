from ninja.errors import HttpError
from ninja.security import HttpBearer
from rest_framework_simplejwt.authentication import JWTAuthentication
from jwt import ExpiredSignatureError
from rest_framework_simplejwt.exceptions import (
    InvalidToken,
    TokenError,
)


class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        jwt_authentication = JWTAuthentication()
        try:
            validated_token = jwt_authentication.get_validated_token(token)
            user = jwt_authentication.get_user(validated_token)
            if user is None:
                raise HttpError(403, "Authentication failed: Unable to identify user.")
            return user
        except ExpiredSignatureError:
            raise HttpError(401, "The token has expired. Please log in again.")
        except TokenError as e:
            raise HttpError(401, f"Token error: {str(e)}")
        except InvalidToken:
            raise HttpError(401, "Invalid token provided.")
