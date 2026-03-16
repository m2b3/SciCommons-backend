import logging

from celery.result import AsyncResult
from ninja import Router
from ninja.responses import codes_4xx, codes_5xx

from articles.models import Article
from articles.schemas import Message
from myapp.celery import app as celery_app
from myapp.services.ai_tasks import analyse_article_task
from users.auth import JWTAuth

router = Router(tags=["Article AI"])

logger = logging.getLogger(__name__)


@router.post(
    "/{article_slug}/ai-summarize",
    response={202: dict, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def queue_ai_analysis(request, article_slug: str):
    """Queue an AI-powered summary and keyword extraction for an article."""
    try:
        article = Article.objects.get(slug=article_slug)
    except Article.DoesNotExist:
        return 404, {"message": "Article not found."}

    if not article.abstract:
        return 400, {"message": "Article has no abstract to analyse."}

    task = analyse_article_task.delay(article.id, article.abstract)
    return 202, {"task_id": task.id}


@router.get(
    "/ai-task/{task_id}",
    response={200: dict, codes_4xx: Message, codes_5xx: Message},
    auth=JWTAuth(),
)
def get_ai_task_result(request, task_id: str):
    """Poll the status of a queued AI analysis task."""
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return 200, {"status": "pending", "result": None}
    if task.state == "FAILURE":
        return 200, {"status": "failed", "result": None}
    if task.successful():
        return 200, {"status": "complete", "result": task.result}
    return 200, {"status": task.state.lower(), "result": None}
