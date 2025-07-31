from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


@shared_task(bind=True, max_retries=3)
def send_email_task(
    self,
    subject,
    html_template_name="",
    context={},
    recipient_list=[],
    from_email=None,
    is_html=True,
    message="",
):
    """Task to send an email asynchronously, with support for HTML content."""
    try:
        if is_html:
            html_content = render_to_string(html_template_name, context)
            text_content = strip_tags(html_content)

            send_mail(
                subject,
                text_content,
                from_email,
                recipient_list,
                html_message=html_content,
            )

        else:
            print(message)
            send_mail(subject, message, from_email, recipient_list)

    except Exception as exc:
        # Retry task in case of failure
        raise self.retry(exc=exc, countdown=60)
