from fastapi import APIRouter

from digitalcard.api.routes.admin_users import router as admin_router
from digitalcard.api.routes.auth import router as auth_router
from digitalcard.api.routes.cards import router as cards_router
from digitalcard.api.routes.employees import router as employees_router
from digitalcard.api.routes.health import router as health_router
from digitalcard.api.routes.platform_companies import router as platform_companies_router
from digitalcard.api.routes.public_cards import router as public_cards_router
from digitalcard.api.routes.public_employees import router as public_employees_router
from digitalcard.api.routes.tenant_organization import router as tenant_organization_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(admin_router)
api_router.include_router(platform_companies_router)
api_router.include_router(tenant_organization_router)
api_router.include_router(employees_router)
api_router.include_router(public_employees_router)
api_router.include_router(cards_router)
api_router.include_router(public_cards_router)
