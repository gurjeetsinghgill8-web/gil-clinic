"""FastAPI route modules: auth, users, sessions, roles, permissions."""

from src.presentation.identity.routes.auth_routes import router as auth_router
from src.presentation.identity.routes.user_routes import router as user_router
from src.presentation.identity.routes.session_routes import router as session_router

__all__ = [
    "auth_router",
    "user_router",
    "session_router",
]
