import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.fullmatch(value):
        raise ValueError("Enter a valid email address.")
    return value


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("Name is required.")
    return value


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ValueError("Password must contain at least one letter and one number.")
    return value


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=254)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)

    _name = field_validator("name")(_clean_name)
    _email = field_validator("email")(_clean_email)
    _password = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class CodeRequest(BaseModel):
    email: str = Field(max_length=254)

    _email = field_validator("email")(_clean_email)


class CodeVerify(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    name: str | None = Field(default=None, max_length=100)

    _email = field_validator("email")(_clean_email)

    @field_validator("code")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class VerificationPending(BaseModel):
    """Returned instead of a signed-in user when the email still has to be confirmed with a code."""

    verification_required: Literal[True] = True
    email: str
    expires_in_seconds: int
    resend_after_seconds: int


class Preferences(BaseModel):
    home_airport: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    cabin: Literal["Economy", "Premium economy", "Business", "First class"] | None = None
    passengers: int | None = Field(default=None, ge=1, le=9)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    theme: Literal["light", "dark", "system"] | None = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    preferences: Preferences
    created_at: datetime
    email_verified: bool = False
    has_password: bool = True


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return None if value is None else _clean_email(value)


class PasswordChange(BaseModel):
    # Not needed when the account has no password yet (created by code sign-in).
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(max_length=MAX_PASSWORD_LENGTH)

    _new = field_validator("new_password")(_check_password)


class DeleteAccountRequest(BaseModel):
    # Required when the account has a password; passwordless accounts confirm with "DELETE" alone.
    password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)
    confirm: Literal["DELETE"]


class SaveFlightRequest(BaseModel):
    offer: dict[str, Any]
    search: dict[str, Any] | None = None

    @field_validator("offer")
    @classmethod
    def _offer_has_id(cls, value: dict[str, Any]) -> dict[str, Any]:
        offer_id = value.get("id")
        if not isinstance(offer_id, str) or not offer_id or len(offer_id) > 100:
            raise ValueError("Offer must include a valid id.")
        for key in ("airline", "price", "currency", "origin", "destination"):
            if key not in value:
                raise ValueError(f"Offer is missing '{key}'.")
        return value


class SavedFlightOut(BaseModel):
    id: int
    offer_id: str
    offer: dict[str, Any]
    search: dict[str, Any] | None
    saved_at: datetime


class FavouriteRequest(BaseModel):
    airport_code: str = Field(pattern=r"^[A-Z]{3}$")


class SavedRouteRequest(BaseModel):
    origin: str = Field(pattern=r"^[A-Z]{3}$")
    destination: str = Field(pattern=r"^[A-Z]{3}$")
