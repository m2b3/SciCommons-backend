"""
This file contains the API endpoints related to user management.
"""

from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from ninja import Router
from ninja.errors import HttpError, HttpRequest
from ninja.responses import codes_4xx
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from myapp.schemas import Message
from myapp.services.send_emails import send_email_task
from users.models import Reputation, User
from users.schemas import (
    LogInSchemaIn,
    LogInSchemaOut,
    ResetPasswordSchema,
    UserCreateSchema,
)

router = Router(tags=["Users Auth"])
signer = TimestampSigner()

refresh_expiry = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
debug = settings.DEBUG

cookieSettings = {
    "httponly": True,
    "secure": not debug,
    "samesite": 'lax',
    "domain": settings.COOKIE_DOMAIN,
    "path": '/',
    "max_age": refresh_expiry,
}

@router.post("/signup", response={201: Message, 400: Message})
def signup(request: HttpRequest, payload: UserCreateSchema):
    if payload.password != payload.confirm_password:
        return 400, {"message": "Passwords do not match."}

    user = User.objects.filter(email=payload.email).first()

    if user:
        if not user.is_active:
            return 400, {
                "message": "Email already registered but not activated. Please check your email for the activation link."
            }
        else:
            return 400, {"message": "Email is already in use."}

    if User.objects.filter(username=payload.username).exists():
        return 400, {"message": "Username is already taken."}

    try:
        user = User.objects.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        user.is_active = False

        user.save()

        # Generate a token
        token = signer.sign(user.pk)

        link = f"{settings.FRONTEND_URL}/auth/activate/{token}"

        # Render the HTML template with context
        html_content = {
            "name": user.first_name,
            "activation_link": link,
        }

        send_email_task.delay(
            subject="Activate your account",
            html_template_name="activation_email.html",
            context=html_content,
            recipient_list=[payload.email]
        )

    except IntegrityError:
        raise HttpError(500, "User could not be created.")

    return 201, {
        "message": (
            "Account created successfully. Please check your email to activate your account."
        )
    }

@router.post("/activate/{token}", response={200: Message, 400: Message, 404: Message})
def activate(request: HttpRequest, token: str):
    try:
        # Extract the user ID from the token and check expiration
        user_id = signer.unsign(token, max_age=1800)  # 1800 seconds = 30 minutes
        user = User.objects.get(pk=user_id)

        if user.is_active:
            return 400, {"message": "Account already activated."}

        # Create Reputation object for the user
        Reputation.objects.get_or_create(user=user)

        user.is_active = True
        user.save()

        return 200, {"message": "Account activated successfully."}

    except SignatureExpired:
        return 400, {"message": "Activation link expired."}

    except BadSignature:
        return 400, {"message": "Invalid activation link."}

@router.post("/resend-activation/{email}", response={200: Message, 400: Message, 404: Message})
def resend_activation(request: HttpRequest, email: str):
    try:
        user = User.objects.get(email=email)

        if user.is_active:
            return 400, {"message": "This account is already active. Consider logging in."}

        # Generate a new and unique activation token
        token = signer.sign(user.pk)
        link = f"{settings.FRONTEND_URL}/auth/activate/{token}"

        html_content = {
            "name": user.first_name,
            "activation_link": link,
        }

        send_email_task.delay(
            subject="Activate your account",
            html_template_name="resend_activation_email.html",
            context=html_content,
            recipient_list=[email]
        )

    except User.DoesNotExist:
        return 404, {"message": "No account associated with this email was found."}

    return 200, {"message": "Activation link sent. Please check your email."}

@router.post("/login", response={200: LogInSchemaOut, codes_4xx: Message})
def login_user(request, payload: LogInSchemaIn):
    # Attempt to retrieve user by username or email
    user = (
        User.objects.filter(username=payload.login).first()
        or User.objects.filter(email=payload.login).first()
    )
    if not user:
        return 404, {"message": "No account found with the provided username/email."}

    if not user.is_active:
        return 403, {"message": "This account is inactive. Please activate your account."}

    # Authenticate the user
    user = authenticate(username=user.username, password=payload.password)
    if user is None:
        return 401, {"message": "Invalid password."}

    login(request, user)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    access_expiry = int((datetime.now() + settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]).timestamp() * 1000)


    response = JsonResponse(
        {
            "status": "success",
            "message": "Login successful.",
            "token": access_token,
            "expiresAt": access_expiry,
            "cookie": cookieSettings
        }
    )

    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        **cookieSettings
    )

    return response

@router.post("/refresh", response={200: Message, 401: Message})
def refresh_token(request: HttpRequest):
    try:
        refresh_token = request.COOKIES.get("refreshToken")
        if not refresh_token:
            return 401, {"message": "Refresh token is missing."}
        
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)
        access_expiry = int((datetime.now() + settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]).timestamp() * 1000)


        # Invalidate the old token if BLACKLIST_AFTER_ROTATION is True
        # if settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"]:
        #     try:
        #         refresh.blacklist()
        #     except Exception as e:
        #         print(f"Error blacklisting refresh token: {str(e)}")

        response = JsonResponse(
            {
                "status": "success",
                "message": "Token refreshed successfully.",
                "token": access_token,
                "expiresAt": access_expiry,
                "cookie": cookieSettings
            }
        )

        response.set_cookie( 
            key="refreshToken",
            value=new_refresh_token,
            **cookieSettings
        )
        
        return response

    except TokenError as e:
        print('TokenError', e)
        return 401, {"message": f"Token error: {str(e)}"}
    except InvalidToken:
        print('TokenError', InvalidToken)
        return 401, {"message": "Invalid refresh token."}
    except Exception as e:
        print('TokenError', e)
        return 401, {"message": "Invalid refresh token."}

@router.post("/forgot-password/{email}", response={200: Message, 404: Message})
def request_reset(request: HttpRequest, email: str):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return 404, {"message": "No user found with this email address."}

    # Encode user's primary key and sign it with a timestamp
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    signed_uid = signer.sign(uid)

    # Generate a reset link
    reset_link = f"{settings.FRONTEND_URL}/auth/resetpassword/{signed_uid}"

    html_content = {
        "name": user.first_name,
        "reset_link": reset_link,
    }

    send_email_task.delay(
        subject="Password Reset Request",
        html_template_name="password_reset_email.html",
        context=html_content,
        recipient_list=[user.email]
    )

    return 200, {"message": "Password reset link has been sent to your email."}

@router.post("/reset-password/{token}", response={200: Message, 400: Message})
def reset_password(request: HttpRequest, token: str, payload: ResetPasswordSchema):
    try:
        # Unsign to verify the token and extract the UID
        original_uid = signer.unsign(token, max_age=3600)  # Token expires after 1 hour
        uid = urlsafe_base64_decode(original_uid).decode()
        user = User.objects.get(pk=uid)

        # Check if passwords match
        if payload.password != payload.confirm_password:
            return 400, {"message": "Passwords do not match."}

        # Set the new password
        user.set_password(payload.password)
        user.save()

        return 200, {"message": "Password reset successfully."}

    except SignatureExpired:
        return 400, {"message": "Password reset link expired."}

    except BadSignature:
        return 400, {"message": "Invalid password reset link."}
    
@router.get("/logout", response={200: Message})
def logout(request: HttpRequest):
    refresh_token = request.COOKIES.get("refreshToken")
    if refresh_token:
        if settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"]:
            try:
                refresh = RefreshToken(refresh_token)
                refresh.blacklist()
            except Exception as e:
                print(f"Error blacklisting refresh token: {str(e)}")

    response = JsonResponse(
        {
            "status": "success",
            "message": "Logout successful."
        }
    )
    
    return response
