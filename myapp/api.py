from ninja import NinjaAPI, Router

from communities.api import router as communities_router
from communities.posts_comments_api import router as communities_posts_comments_router
from users.api import router as users_router

api = NinjaAPI()

# Create a parent router to aggregate all community-related endpoints
communities_parent_router = Router()

communities_parent_router.add_router("", communities_router)
communities_parent_router.add_router("", communities_posts_comments_router)

api.add_router("/users", users_router)
api.add_router("/communities", communities_parent_router)
