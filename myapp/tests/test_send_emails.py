from django.core import mail
from django.test import TestCase

from myapp.services.send_emails import send_email_task


class SendEmailTaskTestCase(TestCase):
    def test_renders_and_sends_activation_email(self):
        activation_link = "https://frontend.example/auth/activate/signed-token"

        send_email_task.run(
            subject="Activate your account",
            html_template_name="activation_email.html",
            context={"name": "Ada", "activation_link": activation_link},
            recipient_list=["ada@example.invalid"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Activate your account")
        self.assertEqual(email.to, ["ada@example.invalid"])
        self.assertEqual(email.content_subtype, "html")
        self.assertIn("Hi Ada", email.body)
        self.assertIn(activation_link, email.body)

    def test_renders_and_sends_password_reset_email(self):
        reset_link = "https://frontend.example/auth/resetpassword/signed-token"

        send_email_task.run(
            subject="Password Reset Request",
            html_template_name="password_reset_email.html",
            context={"name": "Grace", "reset_link": reset_link},
            recipient_list=["grace@example.invalid"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Password Reset Request")
        self.assertEqual(email.to, ["grace@example.invalid"])
        self.assertEqual(email.content_subtype, "html")
        self.assertIn("Hi Grace", email.body)
        self.assertIn(reset_link, email.body)
