import logging
from urllib.parse import quote

from celery import shared_task
from decouple import config
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from users.settings_cache import is_email_notifications_enabled

logger = logging.getLogger(__name__)


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
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL

        if is_html:
            html_content = render_to_string(html_template_name, context)
            text_content = strip_tags(html_content)

            # Use EmailMessage for better control over headers
            from django.core.mail import EmailMessage

            email = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=from_email,
                to=recipient_list,
            )
            email.content_subtype = "html"

            # Add headers to help prevent spam
            email.extra_headers = {
                "X-Priority": "3",  # Normal priority
                "X-MSMail-Priority": "Normal",
                "Importance": "normal",
            }

            email.send()

        else:
            print(message)
            send_mail(subject, message, from_email, recipient_list)

    except Exception as exc:
        # Retry task in case of failure
        raise self.retry(exc=exc, countdown=60)


def get_frontend_domain():
    """Get the frontend domain based on environment."""
    environment = config("ENVIRONMENT", default="local").lower()
    if environment == "production" or environment == "prod":
        return "https://alphatest.scicommons.org"
    elif environment == "staging" or environment == "test":
        return "https://test.scicommons.org"
    else:
        # For local development, use FRONTEND_URL if available
        return getattr(settings, "FRONTEND_URL", "http://localhost:3000")


def send_review_notification_email(article, review, community):
    """
    Send email notification to article submitter when a new review is added.
    Only for articles in a community.
    Respects user's email notification settings.
    """
    if not community:
        return

    try:
        recipient = article.submitter
        if not recipient or not recipient.email:
            logger.warning(
                f"Cannot send review notification: recipient has no email for article {article.id}"
            )
            return

        # Don't send email if reviewer is the submitter
        if review.user == recipient:
            return

        # Check if recipient has email notifications enabled
        if not is_email_notifications_enabled(recipient.id):
            logger.debug(
                f"Email notifications disabled for user {recipient.id}, skipping review notification"
            )
            return

        domain = get_frontend_domain()
        article_link = f"{domain}/community/{quote(community.name, safe='')}/articles/{article.slug}"

        # Truncate content for preview (first 200 characters)
        content_preview = (
            review.content[:200] + "..."
            if len(review.content) > 200
            else review.content
        )

        context = {
            "recipient_name": recipient.first_name or recipient.username,
            "notification_type": "New Review on Your Article",
            "message_text": mark_safe(
                f"<b>{review.user.username}</b> has posted a new review on your article "
                f'<em>"{article.title}"</em> in the <b>{community.name}</b> community.'
            ),
            "content_preview": content_preview,
            "article_link": article_link,
        }

        send_email_task.delay(
            subject=f"New Review on Your Article: {article.title}",
            html_template_name="review_comment_notification.html",
            context=context,
            recipient_list=[recipient.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
        )
    except Exception as e:
        logger.error(f"Error sending review notification email: {e}")


def send_join_request_email(user, community):
    admin = community.admins.first()
    if not admin or not admin.email:
        logger.warning(
            f"Cannot send join request email: community {community.id} has no admin with email"
        )
        return

    if not is_email_notifications_enabled(admin.id):
        logger.debug(
            f"Email notifications disabled for admin {admin.id}, skipping join request email"
        )
        return

    domain = get_frontend_domain()
    link = f"{domain}/community/{quote(community.name, safe='')}/requests"

    context = {
        "recipient_name": admin.first_name or admin.username,
        "notification_type": "New Join Request",
        "message_text": mark_safe(
            f"<b>{user.username}</b> has requested to join the <b>{community.name}</b> community."
        ),
        "content_preview": None,
        "article_link": link,
    }

    send_email_task.delay(
        subject=f"New Join Request for {community.name}",
        html_template_name="review_comment_notification.html",
        context=context,
        recipient_list=[admin.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
    )


def send_join_decision_email(user, community, action):
    if not user or not user.email:
        logger.warning(
            f"Cannot send join decision email: user has no email for community {community.id}"
        )
        return

    if not is_email_notifications_enabled(user.id):
        logger.debug(
            f"Email notifications disabled for user {user.id}, skipping join decision email"
        )
        return

    domain = get_frontend_domain()

    if action == "approve":
        notification_type = "Join Request Approved"
        message_text = mark_safe(
            f"Your request to join <b>{community.name}</b> has been approved. Welcome!"
        )
        link = f"{domain}/community/{quote(community.name, safe='')}"
    else:
        notification_type = "Join Request Rejected"
        message_text = mark_safe(
            f"Your request to join <b>{community.name}</b> has been rejected."
        )
        link = f"{domain}/communities"

    context = {
        "recipient_name": user.first_name or user.username,
        "notification_type": notification_type,
        "message_text": message_text,
        "content_preview": None,
        "article_link": link,
    }

    send_email_task.delay(
        subject=f"Community Join Request {action.capitalize()}d: {community.name}",
        html_template_name="review_comment_notification.html",
        context=context,
        recipient_list=[user.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
    )


def send_comment_notification_email(comment, review, article, community):
    """
    Send email notification when a new comment/reply is added to a review.
    Email goes to:
    - Review author if it's a top-level comment
    - Comment author if it's a reply to a comment
    Only for articles in a community.
    Respects user's email notification settings.
    """
    if not community:
        return

    try:
        # Determine recipient: review author for top-level comments, parent comment author for replies
        if comment.parent:
            recipient = comment.parent.author
            notification_type = "New Reply to Your Comment"
            # Don't send email if user is replying to their own comment
            if comment.author == recipient:
                return
            message_text = mark_safe(
                f"<b>{comment.author.username}</b> has replied to your comment on the review "
                f'of <em>"{article.title}"</em> in the <b>{community.name}</b> community.'
            )
        else:
            recipient = review.user
            notification_type = "New Comment on Your Review"
            # Don't send email if user is commenting on their own review
            if comment.author == recipient:
                return
            message_text = mark_safe(
                f"<b>{comment.author.username}</b> has commented on your review "
                f'of <em>"{article.title}"</em> in the <b>{community.name}</b> community.'
            )

        if not recipient or not recipient.email:
            logger.warning(
                f"Cannot send comment notification: recipient has no email for comment {comment.id}"
            )
            return

        # Check if recipient has email notifications enabled
        if not is_email_notifications_enabled(recipient.id):
            logger.debug(
                f"Email notifications disabled for user {recipient.id}, skipping comment notification"
            )
            return

        domain = get_frontend_domain()
        article_link = f"{domain}/community/{quote(community.name, safe='')}/articles/{article.slug}"

        # Truncate content for preview (first 200 characters)
        content_preview = (
            comment.content[:200] + "..."
            if len(comment.content) > 200
            else comment.content
        )

        context = {
            "recipient_name": recipient.first_name or recipient.username,
            "notification_type": notification_type,
            "message_text": message_text,
            "content_preview": content_preview,
            "article_link": article_link,
        }

        send_email_task.delay(
            subject=f"{notification_type}: {article.title}",
            html_template_name="review_comment_notification.html",
            context=context,
            recipient_list=[recipient.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
        )
    except Exception as e:
        logger.error(f"Error sending comment notification email: {e}")
