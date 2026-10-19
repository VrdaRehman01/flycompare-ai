from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Application liveness check")
def health_check() -> dict[str, str]:
    """Report API process liveness; dependency health is checked separately later."""
    return {"status": "ok", "service": "flycompare-api"}
