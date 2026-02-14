from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django_ratelimit.exceptions import Ratelimited
from ninja import NinjaAPI, Router
from ninja.errors import AuthenticationError, HttpError, HttpRequest, ValidationError

from articles.api import router as articles_router
from articles.discussion_api import router as articles_discussion_router
from articles.review_api import router as articles_review_router
from communities.api import router as communities_router
from communities.api_invitation import router as communities_invitation_router
from communities.api_join import router as communities_join_router
from communities.articles_api import router as communities_posts_router
from communities.members_api import router as communities_admin_router
from myapp.flags_api import router as flags_router
from myapp.realtime_api import router as realtime_router
from posts.api import router as posts_router
from users.api import router as users_general_router
from users.api_auth import router as users_router
from users.common_api import router as users_common_router

api = NinjaAPI(docs_url="docs/", title="MyApp API", urls_namespace="api_v1")

"""
Global Exception Handlers (Error Handlers)
"""


@api.exception_handler(AuthenticationError)
def custom_authentication_error_handler(request, exc):
    return api.create_response(
        request,
        {"message": "Please log in to access this resource."},
        status=401,
    )


@api.exception_handler(Ratelimited)
def ratelimit_exceeded_handler(request, exc):
    return api.create_response(
        request,
        {"message": "Too many requests. Please try again later."},
        status=429,
    )


@api.exception_handler(HttpError)
def custom_http_error_handler(request, exc):
    return api.create_response(
        request, {"message": exc.message}, status=exc.status_code
    )


@api.exception_handler(ValidationError)
def validation_error_handler(request: HttpRequest, exc: ValidationError):
    return api.create_response(request, {"message": exc.errors}, status=422)


@api.exception_handler(ObjectDoesNotExist)
def object_not_found_handler(request, exc):
    # Return a 404 response if the object is not found
    return api.create_response(request, {"message": exc.args[0]}, status=404)


@api.exception_handler(Exception)
def generic_error_handler(request: HttpRequest, exc: Exception):
    if settings.DEBUG:
        error_message = str(exc)
    else:
        error_message = "Internal Server Error"

    return api.create_response(request, {"message": error_message}, status=500)


"""
Registering the routers
"""


# Create a parent router to aggregate all user-related endpoints
users_parent_router = Router()

users_parent_router.add_router("", users_router)
users_parent_router.add_router("", users_general_router)
users_parent_router.add_router("", users_common_router)

# Create a parent router to aggregate all article-related endpoints
articles_parent_router = Router()
articles_parent_router.add_router("", articles_router)
articles_parent_router.add_router("", articles_review_router)
articles_parent_router.add_router("", articles_discussion_router)

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
api.add_router("/realtime", realtime_router)
api.add_router("/flags", flags_router)
# api.add_router("/posts", posts_router)
