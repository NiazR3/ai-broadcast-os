from fastapi import FastAPI
from broadcast.config import Settings
from broadcast.api.routes import router

settings = Settings()
app = FastAPI(title=settings.service_name, version=settings.version)
app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }
