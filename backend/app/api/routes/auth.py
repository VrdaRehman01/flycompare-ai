from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, require_csrf_header
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limit_auth
from app.models import User
from app.schemas.account import LoginRequest, RegisterRequest, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_csrf_header)])


@router.post("/register", response_model=UserOut, status_code=201, dependencies=[Depends(limit_auth)])
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.register(db, body.name, body.email, body.password)
    auth_service.start_session(db, user, response)
    return auth_service.user_out(user)


@router.post("/login", response_model=UserOut, dependencies=[Depends(limit_auth)])
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.authenticate(db, body.email, body.password)
    auth_service.start_session(db, user, response)
    return auth_service.user_out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    auth_service.end_session(db, request.cookies.get(get_settings().session_cookie_name), response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut | None)
def me(user: User | None = Depends(get_current_user_optional)) -> UserOut | None:
    """Return the signed-in user, or null for anonymous visitors."""
    return auth_service.user_out(user) if user else None
