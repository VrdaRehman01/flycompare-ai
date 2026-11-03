"""Price alerts for signed-in users, and the protected endpoint a scheduler calls to check them."""

import hmac
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf_header
from app.core.config import get_settings
from app.core.database import get_db
from app.models import User
from app.services import alert_service

router = APIRouter(tags=["alerts"])


class AlertRequest(BaseModel):
    origin: str = Field(pattern=r"^[A-Z]{3}$")
    destination: str = Field(pattern=r"^[A-Z]{3}$")
    departure_date: date
    return_date: date | None = None
    target_price: float = Field(gt=0, le=1_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def _check(self):
        if self.origin == self.destination:
            raise ValueError("Origin and destination must be different.")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")
        return self


@router.get("/api/account/alerts", summary="Your price alerts")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return alert_service.list_alerts(db, user)


@router.post("/api/account/alerts", status_code=201, summary="Create or update a price alert", dependencies=[Depends(require_csrf_header)])
def create_alert(body: AlertRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return alert_service.create_alert(db, user, body.origin, body.destination, body.departure_date, body.return_date, round(body.target_price, 2), body.currency)


@router.delete("/api/account/alerts/{alert_id}", status_code=204, summary="Remove a price alert", dependencies=[Depends(require_csrf_header)])
def delete_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    alert_service.delete_alert(db, user, alert_id)
    return Response(status_code=204)


@router.post("/api/internal/alerts/run", summary="Check due price alerts (for an external scheduler)", include_in_schema=False)
def run_alerts(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> dict:
    token = get_settings().alerts_cron_token
    supplied = authorization.removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=404, detail="Not Found")  # indistinguishable from a missing route
    return alert_service.run_due(db)
