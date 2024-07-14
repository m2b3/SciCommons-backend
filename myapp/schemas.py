"""
Common schema for all the models
"""

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
    contributed_articles: int
    # communities joined
    communities_joined: int
    # posts created or commented
    contributed_posts: int

    class Config:
        model = User
        model_fields = ["id", "username", "bio", "profile_pic_url", "home_page_url"]

    @staticmethod
    def from_model(user: User):
        # Todo: Change the logic to get the contributed articles and posts
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
            id=user.id,
            username=user.username,
            bio=user.bio,
            profile_pic_url=user.profile_pic_url,
            home_page_url=user.home_page_url,
            reputation_score=Reputation.objects.get(user=user).score,
            reputation_level=Reputation.objects.get(user=user).level,
            contributed_articles=contributed_articles,
            communities_joined=community_joined,
            contributed_posts=contributed_posts,
        )
