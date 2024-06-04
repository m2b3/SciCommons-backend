from ninja import NinjaAPI, Router

from articles.api import router as articles_router
from communities.api import router as communities_router
from communities.posts_comments_api import router as communities_posts_comments_router
from users.api import router as users_router

api = NinjaAPI(docs_url="docs/", title="MyApp API", urls_namespace="api_v1")

# Create a parent router to aggregate all community-related endpoints
communities_parent_router = Router()

communities_parent_router.add_router("", communities_router)
communities_parent_router.add_router("", communities_posts_comments_router)

api.add_router("/users", users_router)
api.add_router("/communities", communities_parent_router)
api.add_router("/articles", articles_router)
