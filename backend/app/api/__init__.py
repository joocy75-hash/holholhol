"""API routers."""

from app.api.auth import router as auth_router
from app.api.rooms import router as rooms_router
from app.api.users import router as users_router

__all__ = [
    "auth_router",
    "rooms_router",
    "users_router",
]
