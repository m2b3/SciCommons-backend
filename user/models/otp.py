from django.db import models


# The `EmailVerify` class is a model in Django that represents an email verification entry, containing
# fields for the user, OTP (one-time password), and an ID.
class EmailVerify(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    otp = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'email_verify'

    def __str__(self) -> str:
        return str(self.id)


# The `ForgetPassword` class represents a model for storing information about forgotten passwords,
# including the user, a one-time password (OTP), and an ID.
class ForgetPassword(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    otp = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'forgot_password'

    def __str__(self) -> str:
        return str(self.id)


__all__ = [
    "EmailVerify",
    "ForgetPassword",
]
