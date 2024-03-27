# The `LoginSerializer` class is a serializer used for validating and authenticating user login
# credentials, and generating access and refresh tokens.
import datetime

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from user.models import User, UserActivity


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, read_only=True)
    password = serializers.CharField(max_length=128, write_only=True)
    access = serializers.CharField(max_length=255, read_only=True)
    refresh = serializers.CharField(max_length=255, read_only=True)
    email = serializers.CharField(max_length=255, read_only=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'id']

    def validate(self, data):
        """
        The `validate` function checks the validity of user credentials (username, email, and password)
        and returns a token for authentication if the credentials are valid.

        :param data: The `data` parameter is the data that needs to be validated. It is a dictionary
        containing the values for the fields `username`, `email`, and `password`
        :return: a dictionary containing the access token and refresh token.
        """
        request = self.context.get('request')
        username = request.data.get("username", None)
        email = request.data.get("email", None)
        password = request.data.get("password", None)
        if username is None and email is None:
            raise serializers.ValidationError(detail={"error": "Username or email must be entered"})

        if username is None and email is not None:
            member = User.objects.filter(email=email).first()
            if member is None:
                raise serializers.ValidationError(detail={"error": "Enter a valid email address"})
            username = member.username

        member = User.objects.filter(username=username).first()
        if member is None:
            raise serializers.ValidationError(
                detail={"error": "Account does not exist. \nPlease try registering to scicommons first"}
            )
        elif member.email_verified == False:
            raise serializers.ValidationError(detail={"error": "Please Verify your Email!!!"})

        user = authenticate(username=username, password=password)

        if user and not user.is_active:
            raise serializers.ValidationError(
                detail={
                    "error": "Account has been deactivated. \n Please contact your company's admin to restore your account"}
            )

        if not user:
            raise serializers.ValidationError(detail={"error": "Username or Password is wrong"})

        refresh = RefreshToken.for_user(user)
        data = {"access": str(refresh.access_token), "refresh": str(refresh)}

        UserActivity.objects.create(user=user, action=f"you Logged in at {datetime.datetime.now()}")

        return data


# The `ForgotPasswordSerializer` class is a serializer for handling forgot password requests, with an
# email field.
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.CharField()

    class Meta:
        fields = ["email"]


# The class `ResetPasswordSerializer` is a serializer class in Python that is used for resetting a
# password and includes fields for OTP, password, and password confirmation.
class ResetPasswordSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    password = serializers.CharField()
    password2 = serializers.CharField()

    class Meta:
        fields = ['otp', 'password', 'password2']


# The above class is a serializer class in Python used for verifying OTP and email.
class VerifySerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    email = serializers.CharField()

    class Meta:
        fields = ['otp', 'email']


__all__ = [
    "LoginSerializer",
    "ForgotPasswordSerializer",
    "ResetPasswordSerializer",
    "VerifySerializer",
]
