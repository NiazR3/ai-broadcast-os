from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from broadcast.config import Settings
from broadcast.api.routes import router
from broadcast.agents.router import router as agent_router
from broadcast.middleware.rate_limit import RateLimitMiddleware
from broadcast.middleware.security_headers import SecurityHeadersMiddleware

settings = Settings()
app = FastAPI(title=settings.service_name, version=settings.version)

# -- Security middleware (applied to all responses) ---------------------------
app.add_middleware(SecurityHeadersMiddleware)

# -- Rate limiting (applied to /broadcast/* routes) ---------------------------
app.add_middleware(RateLimitMiddleware, default_limit=120, post_limit=30, window_seconds=60)

# -- CORS --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(agent_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }
