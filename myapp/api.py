from ninja import NinjaAPI, Router
from ninja.errors import AuthenticationError, HttpError

from articles.api import router as articles_router
from articles.api_review import router as articles_review_router
from communities.api import router as communities_router
from communities.api_admin import router as communities_admin_router
from communities.api_invitation import router as communities_invitation_router
from communities.api_join import router as communities_join_router
from communities.api_posts import router as communities_posts_router
from users.api import router as users_general_router
from users.api_auth import router as users_router

api = NinjaAPI(docs_url="docs/", title="MyApp API", urls_namespace="api_v1")


@api.exception_handler(AuthenticationError)
def custom_authentication_error_handler(request, exc):
    return api.create_response(
        request,
        {"message": "You need to be authenticated to perform this action."},
        status=401,
    )


@api.exception_handler(HttpError)
def custom_http_error_handler(request, exc):
    return api.create_response(
        request, {"message": exc.message}, status=exc.status_code
    )


# Create a parent router to aggregate all user-related endpoints
users_parent_router = Router()

users_parent_router.add_router("", users_router)
users_parent_router.add_router("", users_general_router)

# Create a parent router to aggregate all article-related endpoints
articles_parent_router = Router()
articles_parent_router.add_router("", articles_router)
articles_parent_router.add_router("", articles_review_router)

# Create a parent router to aggregate all community-related endpoints
communities_parent_router = Router()

communities_parent_router.add_router("", communities_router)
communities_parent_router.add_router("", communities_invitation_router)
communities_parent_router.add_router("", communities_admin_router)
communities_parent_router.add_router("", communities_posts_router)
communities_parent_router.add_router("", communities_join_router)

api.add_router("/users", users_parent_router)
api.add_router("/articles", articles_parent_router)
api.add_router("/communities", communities_parent_router)
