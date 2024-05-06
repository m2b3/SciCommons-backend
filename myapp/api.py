from ninja import NinjaAPI

from users.api import router as users_router

api = NinjaAPI()

api.add_router("/users", users_router)
