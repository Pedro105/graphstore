"""FastAPI application skeleton: health/readiness endpoints and app wiring.

Business endpoints (remember/recall/etc.) are not implemented yet — see
CLAUDE.md for what's deferred to later phases.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from contextstore.api.admin_routes import router as admin_router
from contextstore.api.routes import router
from contextstore.core.config import get_settings
from contextstore.db import postgres
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.vector.embeddings import OpenAIEmbeddingProvider

APP_VERSION = "0.1.0"

settings = get_settings()

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
        if settings.environment == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelNamesMapping()[settings.log_level.upper()]
    ),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.graph_store = FalkorDBGraphStore(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        password=(
            settings.falkordb_password.get_secret_value() if settings.falkordb_password else None
        ),
    )
    app.state.embedding_provider = OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )
    # Postgres pool backs auth (api/auth.py). Created only when DATABASE_URL is
    # set; when it isn't, app.state.db_pool stays None and the /v1/ routes
    # return 503 rather than running unauthenticated (see get_db).
    if settings.database_url is not None:
        app.state.db_pool = await postgres.create_pool(settings.database_url.get_secret_value())
    else:
        app.state.db_pool = None
        logger.warning("app_startup.no_database_url", detail="auth disabled; /v1 routes return 503")
    logger.info(
        "app_startup", falkordb_host=settings.falkordb_host, falkordb_port=settings.falkordb_port
    )
    yield
    if app.state.db_pool is not None:
        await app.state.db_pool.close()
    await app.state.graph_store.aclose()
    logger.info("app_shutdown")


app = FastAPI(
    title="ContextStore API",
    version=APP_VERSION,
    description="GraphRAG-based memory layer for AI workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(admin_router)


async def _postgres_ok() -> bool:
    """True if the auth Postgres pool answers a trivial query. A None pool means
    DATABASE_URL is unset (auth deliberately disabled) -- that's not a failure
    here; see `/health` for how it's reported."""
    pool = app.state.db_pool
    if pool is None:
        return True
    try:
        return bool(await pool.fetchval("SELECT 1") == 1)
    except Exception:
        return False


@app.get("/health")
async def health(response: Response) -> dict[str, object]:
    """Liveness+dependency probe used by Fly health checks. 200 when both
    Postgres and FalkorDB are reachable; 503 if either configured dependency is
    down. Unauthenticated and cheap so it can be polled frequently."""
    falkordb_ok = await app.state.graph_store.health_check()
    postgres_reachable = await _postgres_ok()
    postgres_configured = app.state.db_pool is not None

    checks = {
        "falkordb": "ok" if falkordb_ok else "unreachable",
        "postgres": ("ok" if postgres_reachable else "unreachable")
        if postgres_configured
        else "not_configured",
    }
    healthy = falkordb_ok and postgres_reachable
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "version": APP_VERSION, "checks": checks}


@app.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    is_healthy = await app.state.graph_store.health_check()
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"falkordb": "unavailable"}
    return {"falkordb": "ok"}
