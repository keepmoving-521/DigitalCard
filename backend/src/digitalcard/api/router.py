from fastapi import APIRouter

from digitalcard.api.routes.admin_users import router as admin_router
from digitalcard.api.routes.auth import router as auth_router
from digitalcard.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(admin_router)
