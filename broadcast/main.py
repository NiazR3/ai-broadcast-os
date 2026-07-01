import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.requests import Request
from broadcast.config import Settings
from broadcast.api.routes import router
from broadcast.agents.router import router as agent_router, start_agents, stop_agents
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
from broadcast.auth import verify_api_key

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start analytics and broadcast agents on boot, stop on shutdown."""
    start_agent()
    start_agents()
    yield
    stop_agents()
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

# API routers - verify_api_key is already applied via router dependencies
app.include_router(router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(audience_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(media_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }


# -- Dashboard SPA (served from same server, no CORS issues) -------------------
_dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
_dashboard_index = os.path.join(_dashboard_dir, "index.html")
if os.path.isdir(_dashboard_dir) and os.path.isfile(_dashboard_index):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_dashboard_dir, "assets")),
        name="dashboard_assets",
    )

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(os.path.join(_dashboard_dir, "favicon.svg"))

    # SPA fallback: any unmatched non-API path serves index.html
    @app.exception_handler(HTTPException)
    async def spa_fallback(request: Request, exc: HTTPException):
        if exc.status_code != 404:
            return JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code
            )
        # Return JSON 404 for API-like paths
        for prefix in ("/api", "/agent", "/broadcast", "/audience", "/research", "/media", "/analytics", "/health", "/metrics", "/docs", "/openapi.json", "/redoc"):
            if request.url.path.startswith(prefix):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
        # Everything else → SPA
        return FileResponse(os.path.join(_dashboard_dir, "index.html"))
