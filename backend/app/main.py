from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.account import router as account_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.flights import router as flights_router
from app.api.routes.health import router as health_router
from app.api.routes.insights import router as insights_router
from app.api.routes.travel import router as travel_router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.services.alert_service import AlertScheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.is_development and settings.secret_key == "dev-only-insecure-secret-change-me":
        raise RuntimeError("Set SECRET_KEY to a long random value before running outside development.")
    init_db()
    scheduler = None
    if settings.alerts_enabled and settings.alerts_check_interval_minutes > 0 and settings.app_env.strip().lower() != "test":
        scheduler = AlertScheduler(SessionLocal, settings.alerts_check_interval_minutes)
        scheduler.start()
    yield
    if scheduler:
        scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Intelligent flight comparison and travel decision support. "
        "Historical/demo data will be labeled explicitly; it is not live availability."
    ),
    version="0.2.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
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
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(insights_router)
app.include_router(travel_router)
app.include_router(alerts_router)
