import json
import logging

import requests
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_ollama_base_url():
    return getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")


def _get_ollama_model():
    return getattr(settings, "OLLAMA_MODEL", "llama3.2")


def _call_ollama(prompt: str) -> str:
    """Send a prompt to the local Ollama instance and return the response text."""
    url = f"{_get_ollama_base_url()}/api/generate"
    payload = {
        "model": _get_ollama_model(),
        "prompt": prompt,
        "stream": False,
    }
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["response"].strip()


@shared_task(bind=True, max_retries=2)
def analyse_article_task(self, article_id: int, abstract: str):
    """
    Use a locally hosted Ollama model to summarise an article abstract
    and extract its key topics. Returns a dict with 'summary' and 'keywords'.
    """
    try:
        summary_prompt = (
            f"Summarise the following scientific abstract in 2-3 sentences "
            f"for a general academic audience. Return only the summary text, "
            f"no preamble.\n\nAbstract:\n{abstract}"
        )
        summary = _call_ollama(summary_prompt)

        keyword_prompt = (
            f"Extract 5 to 8 key topic keywords from the following scientific "
            f"abstract. Return them as a JSON array of lowercase strings, "
            f"with no additional text.\n\nAbstract:\n{abstract}"
        )
        raw_keywords = _call_ollama(keyword_prompt)

        try:
            keywords = json.loads(raw_keywords)
            if not isinstance(keywords, list):
                keywords = []
        except json.JSONDecodeError:
            keywords = []

        return {"article_id": article_id, "summary": summary, "keywords": keywords}

    except requests.exceptions.ConnectionError as exc:
        logger.error("Ollama is not reachable at %s: %s", _get_ollama_base_url(), exc)
        raise self.retry(exc=exc, countdown=10)

    except requests.exceptions.Timeout as exc:
        logger.error("Ollama request timed out for article %s: %s", article_id, exc)
        raise self.retry(exc=exc, countdown=30)

    except Exception as exc:
        logger.error("AI analysis failed for article %s: %s", article_id, exc)
        raise
