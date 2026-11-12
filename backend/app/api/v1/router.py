from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.authorization.router import router as authorization_router
from app.modules.identity.router import router as auth_router
from app.modules.identity.users_router import router as users_router
from app.modules.people.router import router as people_router
from app.modules.products.router import router as products_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(people_router)
api_router.include_router(authorization_router)
api_router.include_router(audit_router)
