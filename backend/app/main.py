from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.flights import router as flights_router
from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Intelligent flight comparison and travel decision support. "
        "Historical/demo data will be labeled explicitly; it is not live availability."
    ),
    version="0.1.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", tags=["health"], summary="API root")
def root() -> dict[str, str]:
    """Point visitors at the docs instead of returning a bare 404."""
    return {
        "service": "flycompare-api",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(health_router)
app.include_router(flights_router)
