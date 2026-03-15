from ninja import Router
from django.http import HttpRequest
from ninja.errors import HttpError
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
from articles.models import Article
from communities.models import Membership, Community, CommunityArticle
from users.models import User

router = Router(tags=["Editorial"])

# CRITICAL: load at module level — NOT inside any function
model = SentenceTransformer("all-MiniLM-L6-v2")


class ReviewerSuggestion(BaseModel):
    user_id: int
    username: str
    similarity_score: float
    match_percentage: int


class ReviewerRecommendationResponse(BaseModel):
    article_id: int
    article_title: str
    community_id: int
    article_status: str
    suggestions: list[ReviewerSuggestion]


@router.get("/{article_id}/suggest-reviewers", response=ReviewerRecommendationResponse)
def suggest_reviewers(request: HttpRequest, article_id: int, community_id: int):
    """
    AI-Powered Reviewer Recommendation Endpoint for the GSoC 2026 PoC.
    Returns a ranked list of best-matched reviewers from a community based on 
    semantic similarity between the paper's title/abstract and the reviewers' profiles.
    """
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        raise HttpError(404, "Article not found")

    try:
        community = Community.objects.get(id=community_id)
    except Community.DoesNotExist:
        raise HttpError(404, "Community not found")

    # Get CommunityArticle status
    try:
        ca = CommunityArticle.objects.get(article=article, community=community)
        article_status = ca.status
    except CommunityArticle.DoesNotExist:
        article_status = "not_submitted"

    # Fetch memberships
    memberships = Membership.objects.filter(community=community).select_related("user")
    if not memberships.exists():
        return ReviewerRecommendationResponse(
            article_id=article_id,
            article_title=article.title,
            community_id=community_id,
            article_status=article_status,
            suggestions=[],
        )

    # Build article text and calculate embedding
    article_text = f"{article.title}. {article.abstract or ''}"
    article_embedding = model.encode(article_text, convert_to_tensor=True)

    suggestions_list = []
    
    # Calculate similarities with each member
    for membership in memberships:
        user = membership.user
        user_text = f"{user.username} {user.bio or ''}"
        user_embedding = model.encode(user_text, convert_to_tensor=True)
        
        # Calculate cosine similarity and extract float value
        score = float(util.cos_sim(article_embedding, user_embedding)[0][0])
        
        suggestions_list.append(
            ReviewerSuggestion(
                user_id=user.id,
                username=user.username,
                similarity_score=round(score, 4),
                match_percentage=round(score * 100)
            )
        )

    # Sort descending by similarity score and get top 5
    suggestions_list.sort(key=lambda x: x.similarity_score, reverse=True)
    top_5 = suggestions_list[:5]

    return ReviewerRecommendationResponse(
        article_id=article_id,
        article_title=article.title,
        community_id=community_id,
        article_status=article_status,
        suggestions=top_5,
    )
