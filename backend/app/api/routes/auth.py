from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, require_csrf_header
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limit_auth
from app.models import User
from app.schemas.account import CodeRequest, CodeVerify, LoginRequest, RegisterRequest, UserOut, VerificationPending
from app.services import auth_service, code_service

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_csrf_header)])


def _pending(info: dict) -> JSONResponse:
    return JSONResponse(status_code=202, content=VerificationPending(**info).model_dump())


@router.post("/register", status_code=202, response_model=VerificationPending, dependencies=[Depends(limit_auth)])
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> JSONResponse:
    """Email a verification code; the account is created when the code is entered."""
    return _pending(auth_service.start_registration(db, body.name, body.email, body.password))


@router.post("/login", response_model=UserOut, responses={202: {"model": VerificationPending}}, dependencies=[Depends(limit_auth)])
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Password sign-in. An account whose email is not verified yet gets a code to confirm it first."""
    user = auth_service.authenticate(db, body.email, body.password)
    if user.email_verified_at is None:
        return _pending(code_service.issue(db, user.email, "login"))
    auth_service.start_session(db, user, response)
    return auth_service.user_out(user)


@router.post("/code/request", status_code=202, response_model=VerificationPending, dependencies=[Depends(limit_auth)])
def request_code(body: CodeRequest, db: Session = Depends(get_db)) -> JSONResponse:
    """Email a sign-in code. Same response whether or not the address has an account."""
    return _pending(code_service.issue(db, body.email, "login"))


@router.post("/code/verify", response_model=UserOut, dependencies=[Depends(limit_auth)])
def verify_code(body: CodeVerify, response: Response, db: Session = Depends(get_db)) -> UserOut:
    """Check an emailed code; signs in (creating the account on first use) and verifies the email."""
    row = code_service.verify(db, body.email, body.code)
    user = code_service.account_for(db, row, body.name)
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
