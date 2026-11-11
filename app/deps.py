"""Shared dependencies for the routes."""

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .db import LoginSession, Member
from .events import EventBroker
from .security import token_hash
from .times import now_utc


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def get_broker(request: Request) -> EventBroker:
    return request.app.state.broker


_bearer = HTTPBearer(auto_error=False)


def require_token(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Pushes (Ascrum) and member edits need the API token, when one is configured (API_TOKEN)."""
    if settings.api_token is None:
        return
    if credentials is None or not secrets.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or wrong API token", headers={"WWW-Authenticate": "Bearer"})


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
BrokerDep = Annotated[EventBroker, Depends(get_broker)]
Authorized = Depends(require_token)


# ---- Login ----

#: Set by /api/auth/login and /api/auth/signup; httpOnly, so page scripts can't read it.
SESSION_COOKIE = "autoscrum_session"


def current_member(request: Request, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> Member:
    """The logged-in member, from the session cookie. 401 without a valid session."""
    # Its own short database session: /events streams for hours and must not hold a connection meanwhile.
    with request.app.state.sessions() as session:
        login = session.get(LoginSession, token_hash(token)) if token else None
        member = session.get(Member, login.member_id) if login and login.expires_at > now_utc() else None
    if member is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return member


CurrentMember = Annotated[Member, Depends(current_member)]
LoggedIn = Depends(current_member)


def require_owner(member_id: str, member: CurrentMember) -> None:
    """Members change only their own data (no roles yet). `member_id` is the route's path parameter."""
    if member.id != member_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only change your own plan")


Owner = Depends(require_owner)
