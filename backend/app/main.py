from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, auth, collectors, intel, notifications, ops, rag, security_model, sources, tasks, vulnerabilities
from app.core.config import get_settings
from app.core.input_security import RequestBodyLimitMiddleware
from app.core.security import AuthenticationMiddleware
from app.db import models
from app.db.runtime_schema import ensure_runtime_schema
from app.db.session import Base, engine

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(vulnerabilities.router, prefix=settings.api_v1_prefix)
    app.include_router(ai.router, prefix=settings.api_v1_prefix)
    app.include_router(rag.router, prefix=settings.api_v1_prefix)
    app.include_router(security_model.router, prefix=settings.api_v1_prefix)
    app.include_router(sources.router, prefix=settings.api_v1_prefix)
    app.include_router(collectors.router, prefix=settings.api_v1_prefix)
    app.include_router(intel.router, prefix=settings.api_v1_prefix)
    app.include_router(notifications.router, prefix=settings.api_v1_prefix)
    app.include_router(ops.router, prefix=settings.api_v1_prefix)
    app.include_router(tasks.router, prefix=settings.api_v1_prefix)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": settings.app_name}

    return app


Base.metadata.create_all(bind=engine)
ensure_runtime_schema(engine)
app = create_app()
