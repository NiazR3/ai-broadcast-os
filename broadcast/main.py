from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from broadcast.config import Settings
from broadcast.api.routes import router

settings = Settings()
app = FastAPI(title=settings.service_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }
