"""Identity Engine - Presentation Layer (FastAPI).

Provides:
- REST API routes for authentication (PIN, password, OTP)
- User management routes (CRUD, role assignment)
- Session management routes
- JWT middleware for auth verification
- Request/response schemas (Pydantic v2)
- Dependency injection for use cases
- Error handlers for domain and application exceptions
"""

from src.presentation.identity.routes.auth_routes import router as auth_router
from src.presentation.identity.routes.user_routes import router as user_router

__all__ = [
    "auth_router",
    "user_router",
]
