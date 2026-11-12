from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.deps import CSRF_HEADER
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import CORRELATION_HEADER, OriginCheckMiddleware, RequestContextMiddleware
from app.db.session import dispose_engine
from app.modules.scopes import register_scope_validators


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    register_scope_validators()

    app = FastAPI(
        title="Eranova Orbit API",
        version=__version__,
        description="One company. One command centre.",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    # The last middleware added is the outermost, so RequestContext wraps everything.
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.cors_allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER, CORRELATION_HEADER],
        expose_headers=[CORRELATION_HEADER, "Retry-After"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware, hsts=settings.is_deployed)

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app
