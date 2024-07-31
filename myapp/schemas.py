"""
Common schema for all the models
"""

from datetime import date
from enum import Enum
from typing import Any, Optional

from ninja import ModelSchema, Schema

from articles.models import Article, Review, ReviewComment
from communities.models import Community
from posts.models import Comment, Post
from users.models import Reputation, User


class Tag(Schema):
    value: str
    label: str


# Generic Pagination schema
# The disadvantage of this approach is that proper response schema is not
# generated for the paginated response.


class Message(Schema):
    message: str


class UserStats(ModelSchema):
    reputation_score: int
    reputation_level: str
    # submitted, reviewed or commented articles
    contributed_articles: Optional[int] = None
    # communities joined
    communities_joined: Optional[int] = None
    # posts created or commented
    contributed_posts: Optional[int] = None

    class Config:
        model = User
        model_fields = ["id", "username", "bio", "profile_pic_url", "home_page_url"]

    @staticmethod
    def from_model(user: User, basic_details: bool = False):
        reputation, created = Reputation.objects.get_or_create(user=user)
        basic_data = {
            "id": user.id,
            "username": user.username,
            "profile_pic_url": user.profile_pic_url,
            "reputation_score": reputation.score,
            "reputation_level": reputation.level,
        }

        if basic_details:
            return UserStats(**basic_data)

        contributed_articles = (
            Article.objects.filter(submitter=user).count()
            + Review.objects.filter(user=user).count()
            + ReviewComment.objects.filter(author=user).count()
        )
        contributed_posts = (
            Post.objects.filter(author=user).count()
            + Comment.objects.filter(author=user).count()
        )
        community_joined = Community.objects.filter(members=user).count()

        return UserStats(
            **basic_data,
            bio=user.bio,
            home_page_url=user.home_page_url,
            contributed_articles=contributed_articles,
            communities_joined=community_joined,
            contributed_posts=contributed_posts,
        )


class FilterType(str, Enum):
    POPULAR = "popular"
    RECENT = "recent"
    RELEVANT = "relevant"


class DateCount(Schema):
    date: date
    count: int

    @classmethod
    def json_encode(cls, obj: Any) -> Any:
        if isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        return obj
