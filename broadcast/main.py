from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from broadcast.config import Settings
from broadcast.api.routes import router
from broadcast.agents.router import router as agent_router
from broadcast.audience.router import router as audience_router
from broadcast.research.router import router as research_router
from broadcast.media.router import router as media_router
from broadcast.analytics.router import router as analytics_router
from broadcast.analytics.router import start_agent, stop_agent
from broadcast.middleware.rate_limit import RateLimitMiddleware
from broadcast.middleware.security_headers import SecurityHeadersMiddleware
from broadcast.monitoring.metrics import (
    PrometheusMiddleware,
    metrics_asgi_app,
)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start analytics agent on boot, stop on shutdown."""
    start_agent()
    yield
    stop_agent()


app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)

# -- Security middleware (applied to all responses) ---------------------------
app.add_middleware(SecurityHeadersMiddleware)

# -- HTTP request metrics (applied before rate-limit to count all requests) ---
app.add_middleware(PrometheusMiddleware)

# -- Rate limiting (applied to /broadcast/* routes) ---------------------------
app.add_middleware(RateLimitMiddleware, default_limit=120, post_limit=30, window_seconds=60)

# -- CORS --------------------------------------------------------------------
# In production, set BROADCAST_CORS_ORIGINS to a comma-separated list of allowed origins.
# In dev, defaults to localhost:5173 (Vite dev server).
_cors_origins = settings.cors_origins if settings.cors_origins else ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Prometheus /metrics endpoint (no auth required for scraping) -------------
app.mount("/metrics", metrics_asgi_app, name="metrics")

app.include_router(router)
app.include_router(agent_router)
app.include_router(audience_router)
app.include_router(research_router)
app.include_router(media_router)
app.include_router(analytics_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }
