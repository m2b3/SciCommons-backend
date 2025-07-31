"""
This file contains the API endpoints related to user management.
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from ninja import Router
from ninja.errors import HttpError, HttpRequest
from ninja.responses import codes_4xx, codes_5xx
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

# Module-level logger
logger = logging.getLogger(__name__)


@router.post("/signup", response={201: Message, codes_4xx: Message, codes_5xx: Message})
def signup(request: HttpRequest, payload: UserCreateSchema):
    try:
        if payload.password != payload.confirm_password:
            return 400, {"message": "Passwords do not match."}

        try:
            user = User.objects.filter(email=payload.email).first()

            if user:
                if not user.is_active:
                    return 400, {
                        "message": "Email already registered but not activated. Please"
                        " check your email for the activation link."
                    }
                else:
                    return 400, {"message": "Email is already in use."}
        except Exception as e:
            logger.error(f"Error checking email existence: {e}")
            return 500, {"message": "Error checking email existence. Please try again."}

        try:
            if User.objects.filter(username=payload.username).exists():
                return 400, {"message": "Username is already taken."}
        except Exception as e:
            logger.error(f"Error checking username availability: {e}")
            return 500, {
                "message": "Error checking username availability. Please try again."
            }

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
        except IntegrityError:
            return 500, {"message": "User could not be created. Please try again."}
        except Exception as e:
            logger.error(f"Error creating user account: {e}")
            return 500, {"message": "Error creating user account. Please try again."}

        try:
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
                recipient_list=[payload.email],
            )
        except Exception as e:
            logger.error(f"Error sending activation email: {e}")
            # Continue even if email sending fails - user is created but might need to request activation link again
            pass

        return 201, {
            "message": (
                "Account created successfully. Please check your "
                "email to activate your account."
            )
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/activate/{token}", response={200: Message, codes_4xx: Message, codes_5xx: Message}
)
def activate(request: HttpRequest, token: str):
    try:
        try:
            # Extract the user ID from the token and check expiration
            user_id = signer.unsign(token, max_age=1800)  # 1800 seconds = 30 minutes
        except SignatureExpired:
            return 400, {
                "message": "Activation link expired. Please request a new one."
            }
        except BadSignature:
            return 400, {
                "message": "Invalid activation link. Please request a new one."
            }
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return 500, {"message": "Error verifying token. Please try again."}

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return 404, {"message": "User not found. Please sign up again."}
        except Exception as e:
            logger.error(f"Error retrieving user account: {e}")
            return 500, {"message": "Error retrieving user account. Please try again."}

        if user.is_active:
            return 400, {"message": "Account already activated. You can now log in."}

        try:
            # Create Reputation object for the user
            Reputation.objects.get_or_create(user=user)
        except Exception as e:
            logger.error(f"Error setting up user reputation: {e}")
            return 500, {
                "message": "Error setting up user reputation. Please try again."
            }

        try:
            user.is_active = True
            user.save()
        except Exception as e:
            logger.error(f"Error activating account: {e}")
            return 500, {"message": "Error activating account. Please try again."}

        return 200, {"message": "Account activated successfully. You can now log in."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/resend-activation/{email}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def resend_activation(request: HttpRequest, email: str):
    try:
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return 404, {"message": "No account associated with this email was found."}
        except Exception as e:
            logger.error(f"Error retrieving user account: {e}")
            return 500, {"message": "Error retrieving user account. Please try again."}

        if user.is_active:
            return 400, {
                "message": "This account is already active. You can log in now."
            }

        try:
            # Generate a new and unique activation token
            token = signer.sign(user.pk)
            link = f"{settings.FRONTEND_URL}/auth/activate/{token}"

            # Render the HTML template with context
            html_content = {
                "name": user.first_name,
                "activation_link": link,
            }

            # Send email
            send_email_task.delay(
                subject="Activate your account",
                html_template_name="resend_activation_email.html",
                context=html_content,
                recipient_list=[email],
            )
        except Exception as e:
            logger.error(f"Error sending activation email: {e}")
            return 500, {"message": "Error sending activation email. Please try again."}

        return 200, {"message": "Activation link sent. Please check your email."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/login", response={200: LogInSchemaOut, codes_4xx: Message, codes_5xx: Message}
)
def login_user(request, payload: LogInSchemaIn):
    try:
        try:
            # Attempt to retrieve user by username or email
            user = (
                User.objects.filter(username=payload.login).first()
                or User.objects.filter(email=payload.login).first()
            )
            if not user:
                return 404, {
                    "message": "No account found with the provided username/email."
                }
        except Exception as e:
            logger.error(f"Error retrieving user account: {e}")
            return 500, {"message": "Error retrieving user account. Please try again."}

        # Check if the user's account is active
        if not user.is_active:
            return 403, {
                "message": "This account is inactive. Please activate your account first."
            }

        try:
            # Authenticate the user
            user = authenticate(username=user.username, password=payload.password)
            if user is None:
                return 401, {"message": "Invalid password. Please try again."}
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return 500, {"message": "Authentication error. Please try again."}

        try:
            login(request, user)
        except Exception as e:
            logger.error(f"Error logging in: {e}")
            return 500, {"message": "Error logging in. Please try again."}

        try:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
        except Exception as e:
            logger.error(f"Error generating authentication tokens: {e}")
            return 500, {
                "message": "Error generating authentication tokens. Please try again."
            }

        try:
            response = JsonResponse(
                {
                    "status": "success",
                    "message": "Login successful.",
                    "token": access_token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
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
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return 500, {"message": "Error creating response. Please try again."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/forgot-password/{email}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def request_reset(request: HttpRequest, email: str):
    try:
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return 404, {"message": "No user found with this email address."}
        except Exception as e:
            logger.error(f"Error retrieving user account: {e}")
            return 500, {"message": "Error retrieving user account. Please try again."}

        try:
            # Encode user's primary key and sign it with a timestamp
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            signed_uid = signer.sign(uid)

            # Generate the reset link
            reset_link = f"{settings.FRONTEND_URL}/auth/resetpassword/{signed_uid}"
        except Exception as e:
            logger.error(f"Error generating reset link: {e}")
            return 500, {"message": "Error generating reset link. Please try again."}

        try:
            # Render the HTML template with context
            html_content = {
                "name": user.first_name,
                "reset_link": reset_link,
            }

            send_email_task.delay(
                subject="Password Reset Request",
                html_template_name="password_reset_email.html",
                context=html_content,
                recipient_list=[user.email],
            )
        except Exception as e:
            logger.error(f"Error sending reset email: {e}")
            return 500, {"message": "Error sending reset email. Please try again."}

        return 200, {"message": "Password reset link has been sent to your email."}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}


@router.post(
    "/reset-password/{token}",
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def reset_password(request: HttpRequest, token: str, payload: ResetPasswordSchema):
    try:
        try:
            # Unsign to verify the token and extract the UID
            original_uid = signer.unsign(
                token, max_age=3600
            )  # Token expires after 1 hour
        except SignatureExpired:
            return 400, {
                "message": "Password reset link expired. Please request a new one."
            }
        except BadSignature:
            return 400, {
                "message": "Invalid password reset link. Please request a new one."
            }
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return 500, {"message": "Error verifying token. Please try again."}

        try:
            uid = urlsafe_base64_decode(original_uid).decode()
        except Exception:
            return 400, {
                "message": "Invalid token format. Please request a new password reset link."
            }

        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return 404, {
                "message": "User not found. Please request a new password reset link."
            }
        except Exception as e:
            logger.error(f"Error retrieving user account: {e}")
            return 500, {"message": "Error retrieving user account. Please try again."}

        # Check if passwords match
        if payload.password != payload.confirm_password:
            return 400, {"message": "Passwords do not match. Please try again."}

        try:
            # Set the new password
            user.set_password(payload.password)
            user.save()
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return 500, {"message": "Error updating password. Please try again."}

        return 200, {
            "message": "Password reset successfully. You can now log in with your new password."
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 500, {"message": "An unexpected error occurred. Please try again later."}
