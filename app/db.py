"""Database tables. Times are stored as naive UTC; `times.py` converts them for the team's time zone."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    # FastAPI runs sync endpoints in a thread pool; SQLite has to allow that.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    initials: Mapped[str] = mapped_column(String(4))
    role: Mapped[str] = mapped_column(String(200), default="")
    team: Mapped[str] = mapped_column(String(200), default="")
    avatar_color: Mapped[str] = mapped_column(String(20), default="")
    #: Commits are matched to members by these (git config user.email).
    git_emails: Mapped[list[str]] = mapped_column(JSON, default=list)


class Push(Base):
    """One push to one branch, as sent by Ascrum. Kept for auditing; the app reads commits."""

    __tablename__ = "pushes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pusher_name: Mapped[str] = mapped_column(String(200), default="")
    pusher_email: Mapped[str] = mapped_column(String(320), default="")
    repo: Mapped[str] = mapped_column(String(200))
    branch: Mapped[str] = mapped_column(String(255))
    remote_url: Mapped[str] = mapped_column(String(500), default="")
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    client: Mapped[str] = mapped_column(String(100), default="")

    commits: Mapped[list["Commit"]] = relationship(back_populates="push")


class Commit(Base):
    __tablename__ = "commits"

    sha: Mapped[str] = mapped_column(String(64), primary_key=True)
    push_id: Mapped[int | None] = mapped_column(ForeignKey("pushes.id"))
    author_email: Mapped[str] = mapped_column(String(320), index=True)
    author_name: Mapped[str | None] = mapped_column(String(200))
    repo: Mapped[str] = mapped_column(String(200), index=True)
    branch: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    #: Author date, naive UTC.
    committed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    #: Web page of the commit (GitLab, GitHub...), from the push's remote URL.
    url: Mapped[str | None] = mapped_column(String(600))

    push: Mapped[Push | None] = relationship(back_populates="commits")


class Account(Base):
    """A member's login. At most one per member, made when they sign up with one of their git emails."""

    __tablename__ = "accounts"

    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), primary_key=True)
    #: The email they signed up and log in with, lower case.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    #: From `security.hash_password()`, never the password itself.
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LoginSession(Base):
    """A logged-in browser. Its cookie holds a random token; only the token's SHA-256 is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class DayPlan(Base):
    """What a member typed for one standup day: Today items, blockers, notes, and when they submitted."""

    __tablename__ = "day_plans"

    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: [{text, source, done?}]
    today: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    blockers: Mapped[list[str]] = mapped_column(JSON, default=list)
    resolved_blockers: Mapped[list[str]] = mapped_column(JSON, default=list)
    reviewed: Mapped[dict[str, bool]] = mapped_column(JSON, default=lambda: {"yesterday": False, "blockers": False})
    #: 'HH:mm' in the team's time zone, None while still a draft.
    submitted_at: Mapped[str | None] = mapped_column(String(5))
