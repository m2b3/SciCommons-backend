"""
This file contains the API endpoints related to user management.
"""

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from ninja import Router
from ninja.errors import HttpError, HttpRequest
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from users.schemas import (
    EmailSchema,
    LogInSchemaIn,
    LogInSchemaOut,
    SignUpSchemaIn,
    StatusMessageSchema,
)

router = Router(tags=["Users Auth"])
signer = TimestampSigner()


@router.post("/signup", response=StatusMessageSchema)
def signup(request: HttpRequest, payload: SignUpSchemaIn):
    if payload.password != payload.confirm_password:
        raise HttpError(400, "Passwords do not match.")

    if User.objects.filter(username=payload.username).exists():
        raise HttpError(400, "Username is already taken.")
    user = User.objects.filter(email=payload.email).first()
    if user:
        if not user.is_active:
            raise HttpError(400, "Email already registered but not activated.")
        else:
            raise HttpError(400, "Email is already in use.")

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
        send_mail(
            "Activate your account",
            f"Please click on the link to activate your account: {link}",
            "from@example.com",
            [payload.email],
            fail_silently=False,
        )
    except IntegrityError:
        raise HttpError(500, "User could not be created.")

    return {
        "status": "success",
        "message": "Account created successfully. Please check your email to activate \
            your account.",
    }


@router.get("/activate/{token}", response=StatusMessageSchema)
def activate(request: HttpRequest, token: str):
    try:
        # Extract the user ID from the token and check expiration
        user_id = signer.unsign(token, max_age=1800)  # 1800 seconds = 30 minutes
        user = User.objects.get(pk=user_id)

        if user.is_active:
            raise HttpError(400, "Account already activated.")

        user.is_active = True
        user.save()

    except SignatureExpired:
        raise HttpError(400, "Activation link expired.")

    except BadSignature:
        raise HttpError(400, "Invalid activation link.")

    except User.DoesNotExist:
        raise HttpError(404, "User not found.")

    return {"status": "success", "message": "Account activated successfully."}


@router.post("/resend-activation", response=StatusMessageSchema)
def resend_activation(request: HttpRequest, payload: EmailSchema):
    email = payload.email
    try:
        user = User.objects.get(email=email)

        if user.is_active:
            raise HttpError(
                400, "This account is already active. Consider logging in instead."
            )

        # Generate a new and unique activation token
        token = signer.sign(user.pk)
        link = f"{request.scheme}://{request.get_host()}/activate/{token}"
        send_mail(
            "Activate your account",
            f"Please click on the link to activate your account: {link}",
            "from@example.com",
            [email],
            fail_silently=False,
        )

    except User.DoesNotExist:
        raise HttpError(404, "No account associated with this email was found.")

    return {
        "status": "success",
        "message": "Activation link sent. Please check your email.",
    }


@router.post("/login", response=LogInSchemaOut)
def login_user(request, payload: LogInSchemaIn):
    # Attempt to retrieve user by username or email
    user = (
        User.objects.filter(username=payload.login).first()
        or User.objects.filter(email=payload.login).first()
    )
    if not user:
        raise HttpError(404, "No account found with the provided username/email.")

    # Check if the user's account is active
    if not user.is_active:
        raise HttpError(403, "This account is inactive. Please activate your account.")

    # Authenticate the user
    user = authenticate(username=user.username, password=payload.password)
    if user is None:
        raise HttpError(401, "Invalid password.")

    login(request, user)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)

    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response = JsonResponse(
        {
            "status": "success",
            "message": "Login successful.",
            "token": access_token,
        }
    )

    response.set_cookie(
        key="accessToken",
        value=access_token,
        httponly=True,
        secure=False,  # Ensure secure is False for localhost testing
        samesite="None",  # Adjust for cross-site requests
        max_age=120 * 60,  # 2 hours
    )
    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        httponly=True,
        secure=False,  # Ensure secure is False for localhost testing
        samesite="None",  # Adjust for cross-site requests
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return response


@router.post("/forgot-password", response=StatusMessageSchema)
def request_reset(request: HttpRequest, payload: EmailSchema):
    try:
        user = User.objects.get(email=payload.email)
    except User.DoesNotExist:
        raise HttpError(404, "No user found with this email address.")

    # Encode user's primary key and sign it with a timestamp
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    signed_uid = signer.sign(uid)

    # Send an email with the reset link
    reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{signed_uid}"
    send_mail(
        "Password Reset Request",
        f"Please click on the link below to reset your password:\n{reset_link}",
        "from@example.com",
        [user.email],
        fail_silently=False,
    )

    return {
        "status": "success",
        "message": "Password reset link has been sent to your email.",
    }


@router.post("/reset-password")
def reset_password(
    request: HttpRequest, uidb64: str, new_password: str, confirm_password: str
):
    try:
        # Unsign to verify the token and extract the UID
        original_uid = signer.unsign(uidb64, max_age=3600)  # Token expires after 1 hour
        uid = urlsafe_base64_decode(original_uid).decode()
        user = User.objects.get(pk=uid)

    except SignatureExpired:
        raise HttpError(400, "Activation link expired.")

    except BadSignature:
        raise HttpError(400, "Invalid activation link.")

    except User.DoesNotExist:
        raise HttpError(404, "User not found.")

    # Check if passwords match
    if new_password != confirm_password:
        raise HttpError(400, "Passwords do not match.")

    # Set the new password
    user.set_password(new_password)
    user.save()

    return {
        "status": "success",
        "message": "Your password has been reset successfully.",
    }
