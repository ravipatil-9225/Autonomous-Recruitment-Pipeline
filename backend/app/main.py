"""
FastAPI Application Factory
─────────────────────────────
Main entrypoint for the ARP backend API.
Run with: uvicorn backend.app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from backend.app.config import settings
from backend.app.core.rate_limiter import limiter, rate_limit_handler

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup:
      1. Verify DB connection
      2. Ping Redis
      3. Ensure S3 bucket exists
      4. Verify Chroma connectivity
    Shutdown: close DB connection pool.
    """
    logger.info("🚀 ARP Backend starting up…")

    # 1. Database
    from backend.app.db.session import engine

    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✔ PostgreSQL connected.")
    except Exception as exc:
        logger.error(f"✘ PostgreSQL connection failed: {exc}")

    # 2. Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        logger.info("✔ Redis connected.")
    except Exception as exc:
        logger.warning(f"⚠ Redis not reachable: {exc}")

    # 3. S3 / MinIO bucket
    try:
        from backend.app.services import storage_service

        storage_service.ensure_bucket_exists()
        logger.info("✔ S3/MinIO bucket ready.")
    except Exception as exc:
        logger.warning(f"⚠ S3/MinIO not reachable: {exc}")

    # 4. Chroma
    try:
        import chromadb

        chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        chroma.heartbeat()
        logger.info("✔ Chroma vector DB connected.")
    except Exception as exc:
        logger.warning(f"⚠ Chroma not reachable: {exc}")

    logger.info("✅ ARP Backend ready.")
    yield

    # Shutdown
    logger.info("🛑 ARP Backend shutting down…")
    await engine.dispose()
    logger.info("✔ DB connection pool closed.")


# ── App Factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # ── Routers ───────────────────────────────────────────────────────────
    from backend.app.auth.router import router as auth_router
    from backend.app.routers.admin import router as admin_router
    from backend.app.routers.jobs import router as jobs_router
    from backend.app.routers.pipeline import router as pipeline_router
    from backend.app.routers.resumes import router as resumes_router

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(resumes_router)
    app.include_router(pipeline_router)
    app.include_router(admin_router)

    # ── Static Frontend Dashboard ─────────────────────────────────────────
    import os

    from fastapi.staticfiles import StaticFiles

    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    # ── Health endpoints (public) ─────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": settings.app_version})

    @app.get("/", tags=["Health"], include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            {
                "name": settings.app_title,
                "version": settings.app_version,
                "docs": "/docs",
                "dashboard": "/dashboard/",
            }
        )

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
app = create_app()
