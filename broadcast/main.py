from fastapi import FastAPI
from broadcast.config import Settings

settings = Settings()
app = FastAPI(title=settings.service_name, version=settings.version)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }
