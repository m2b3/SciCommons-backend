from enum import Enum
from typing import List, Optional

from ninja import Query, Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from articles.schemas import ArticleDetails
from users.auth import JWTAuth
from users.models import Notification
from users.schemas import Message, NotificationSchema

router = Router(tags=["Users"], auth=JWTAuth())


class StatusFilter(str, Enum):
    UNSUBMITTED = "unsubmitted"
    PUBLISHED = "published"


# Get my articles
@router.get(
    "/my-articles",
    response={200: List[ArticleDetails], codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_my_articles(request, status_filter: Optional[StatusFilter] = Query(None)):
    try:
        articles = Article.objects.filter(submitter=request.auth).order_by(
            "-created_at"
        )

        if status_filter == StatusFilter.PUBLISHED:
            articles = articles.filter(published=True)
        elif status_filter == StatusFilter.UNSUBMITTED:
            articles = articles.filter(status="Pending", community=None)

        return 200, articles
    except Exception as e:
        return 500, {"message": str(e)}


@router.get(
    "/notifications",
    response={200: List[NotificationSchema], codes_4xx: Message, codes_5xx: Message},
)
def get_notifications(request):
    try:
        user_notifications = Notification.objects.filter(user=request.auth).order_by(
            "-created_at"
        )

        return 200, [
            NotificationSchema(
                **{
                    "id": notif.id,
                    "message": notif.message,
                    "content": notif.content,
                    "isRead": notif.is_read,
                    "link": notif.link,
                    "category": notif.category,
                    "notificationType": notif.notification_type,
                    "createdAt": notif.created_at,
                    "expiresAt": notif.expires_at,
                }
            )
            for notif in user_notifications
        ]
    except Exception as e:
        return 500, {"message": str(e)}


@router.post(
    "/notifications/{notification_id}/mark-as-read",
    auth=JWTAuth(),
    response={200: Message, codes_4xx: Message, codes_5xx: Message},
)
def mark_notification_as_read(request, notification_id: int):
    try:
        notification = Notification.objects.get(pk=notification_id, user=request.auth)
        if not notification:
            return 404, {"message": "Notification does not exist."}

        if not notification.is_read:
            notification.is_read = True
            notification.save()
            return {"message": "Notification marked as read."}
        else:
            return {"message": "Notification was already marked as read."}
    except Exception as e:
        return 500, {"message": str(e)}
