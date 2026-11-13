from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.authorization.router import router as authorization_router
from app.modules.content.router import router as content_router
from app.modules.crm.router import router as crm_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.documents.router import router as documents_router
from app.modules.identity.router import router as auth_router
from app.modules.identity.users_router import router as users_router
from app.modules.integrations.router import router as integrations_router
from app.modules.marketing.router import router as marketing_router
from app.modules.notifications.router import router as notifications_router
from app.modules.nova.router import router as nova_router
from app.modules.people.portal import router as portal_router
from app.modules.people.router import router as people_router
from app.modules.products.router import router as products_router
from app.modules.public.router import router as public_router
from app.modules.reports.router import router as reports_router
from app.modules.support.router import router as support_router
from app.modules.work.router import router as work_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(public_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(content_router)
api_router.include_router(crm_router)
api_router.include_router(people_router)
api_router.include_router(work_router)
api_router.include_router(portal_router)
api_router.include_router(notifications_router)
api_router.include_router(integrations_router)
api_router.include_router(marketing_router)
api_router.include_router(support_router)
api_router.include_router(documents_router)
api_router.include_router(reports_router)
api_router.include_router(nova_router)
api_router.include_router(dashboard_router)
api_router.include_router(authorization_router)
api_router.include_router(audit_router)
