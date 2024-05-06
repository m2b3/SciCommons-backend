"""
This file contains the API endpoints related to user management.
"""

import hashlib

from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from ninja import Router
from ninja.errors import HttpError
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from users.schemas import (
    LogInSchemaIn,
    ResetRequestSchema,
    SignUpSchemaIn,
    SignUpSchemaOut,
)

router = Router()
signer = TimestampSigner()


@router.post("/signup", response=SignUpSchemaOut)
def signup(request, payload: SignUpSchemaIn):
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

        # Generate a token using the userId using hashlib and send it to the user's
        # email
        token = hashlib.sha256(str(user.id).encode()).hexdigest()

        user.activation_token = token
        user.activation_token_created_at = timezone.now()

        user.save()

        link = f"{request.scheme}://{request.get_host()}/activate/{token}"
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
        "message": f"Account created successfully. Activation link is {link}.",
    }


@router.get("/activate/{token}")
def activate(request, token: str):
    try:
        user = User.objects.get(activation_token=token)
    except User.DoesNotExist:
        raise HttpError(404, "Invalid token.")

    if user.activation_token_created_at < timezone.now() - timezone.timedelta(days=1):
        raise HttpError(400, "Token expired. Please sign up again.")

    user.is_active = True
    user.activation_token = None
    user.activation_token_created_at = None
    user.save()

    return {"status": "success", "message": "Account activated successfully."}


@router.post("/login")
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
    user = authenticate(
        username=user.username, password=payload.password
    )  # Authenticate using the username
    if user is None:
        raise HttpError(401, "Invalid password.")

    login(request, user)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)

    tokens = {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }

    return {"status": "success", "message": "Login successful.", "tokens": tokens}


@router.post("/request-reset")
def request_reset(request, payload: ResetRequestSchema):
    try:
        user = User.objects.get(email=payload.email)
    except User.DoesNotExist:
        raise HttpError(404, "No user found with this email address.")

    # Encode user's primary key and sign it with a timestamp
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    signed_uid = signer.sign(uid)

    # Send an email with the reset link
    reset_link = f"http://your-frontend-domain/reset-password/{signed_uid}"
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
def reset_password(request, uidb64: str, new_password: str, confirm_password: str):
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
