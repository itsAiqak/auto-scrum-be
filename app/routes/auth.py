"""Login with email and password. Team members sign up once with one of their git emails; a cookie keeps them logged in."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import Account, LoginSession, Member
from ..deps import SESSION_COOKIE, CurrentMember, SessionDep, SettingsDep
from ..schemas import LogIn, MemberOut, SignUp
from ..security import hash_password, new_token, token_hash, verify_password
from ..times import now_utc
from .members import member_out

router = APIRouter(prefix="/auth", tags=["login"])
SESSION_DAYS = 30
# Only sent to the API's own paths.
COOKIE_PATH = "/api"


@router.post("/signup", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def sign_up(body: SignUp, response: Response, session: SessionDep, settings: SettingsDep) -> MemberOut:
    """Creates the login of the team member who has this email among their git emails, and logs them in."""
    email = body.email.strip().lower()
    matches = [m for m in session.scalars(select(Member)) if email in (e.lower() for e in m.git_emails)]
    if len(matches) != 1:
        detail = "More than one team member has this email." if matches else "This email isn't a team member's git email. Ask your team lead to add it."
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
    member = matches[0]
    if session.get(Account, member.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{member.name} already has an account. Log in instead.")
    session.add(Account(member_id=member.id, email=email, password_hash=hash_password(body.password), created_at=now_utc()))
    _start_session(session, member.id, response, settings)
    return member_out(member)


@router.post("/login", response_model=MemberOut)
def log_in(body: LogIn, response: Response, session: SessionDep, settings: SettingsDep) -> MemberOut:
    account = session.scalar(select(Account).where(Account.email == body.email.strip().lower()))
    if account is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    session.execute(delete(LoginSession).where(LoginSession.member_id == account.member_id, LoginSession.expires_at <= now_utc()))
    _start_session(session, account.member_id, response, settings)
    return member_out(session.get(Member, account.member_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def log_out(response: Response, session: SessionDep, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> None:
    if token:
        session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=MemberOut)
def me(member: CurrentMember) -> MemberOut:
    """Who is logged in. 401 when nobody is: the app then shows its login page."""
    return member_out(member)


def _start_session(session: Session, member_id: str, response: Response, settings: Settings) -> None:
    token = new_token()
    session.add(LoginSession(token_hash=token_hash(token), member_id=member_id, expires_at=now_utc() + timedelta(days=SESSION_DAYS)))
    session.commit()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, path=COOKIE_PATH, httponly=True, samesite="lax", secure=settings.secure_cookies
    )
