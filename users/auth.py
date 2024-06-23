from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class JWTAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token):
        jwt_authentication = JWTAuthentication()
        try:
            validated_token = jwt_authentication.get_validated_token(token)
            user = jwt_authentication.get_user(validated_token)
            if user is None:
                raise HttpError(403, "Authentication failed: Unable to identify user.")
            return user
        except TokenError as e:
            raise HttpError(401, f"Token error: {str(e)}")
        except InvalidToken:
            raise HttpError(401, "Your session has expired. Please log in again.")
        except Exception as e:
            raise HttpError(500, f"Authentication failed: {str(e)}")


# Function-based view to handle partially protected endpoints
def OptionalJWTAuth(request: HttpRequest):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return True  # No token provided, proceed without authentication
    if not auth_header.startswith("Bearer "):
        return True  # Token not in correct format, proceed without authentication

    token = auth_header.split("Bearer ")[1]

    jwt_authentication = JWTAuthentication()
    try:
        validated_token = jwt_authentication.get_validated_token(token)
        user = jwt_authentication.get_user(validated_token)
        if user is None:
            raise HttpError(403, "Authentication failed: Unable to identify user.")
        request.auth = user
        return user
    except TokenError as e:
        raise HttpError(401, f"Token error: {str(e)}")
    except InvalidToken:
        raise HttpError(401, "Your session has expired. Please log in again.")
    except Exception as e:
        raise HttpError(500, f"Authentication failed: {str(e)}")
