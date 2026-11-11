"""Request and response bodies. JSON is camelCase, matching the app's src/app/shared/models/standup.models.ts."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- Pushes (from Ascrum, see ascrum/README.md) ----


class Pusher(Camel):
    name: str = ""
    email: str = ""


class PushedCommit(Camel):
    sha: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    author_email: str = ""
    author_name: str | None = None
    #: Subject line.
    message: str = Field(default="", max_length=2000)
    #: Author date, ISO 8601 (with offset; without one it is taken as team-local time).
    timestamp: datetime
    files_changed: int = Field(default=0, ge=0)


class PushIn(Camel):
    pusher: Pusher = Pusher()
    repo: str = Field(min_length=1, max_length=200)
    remote_url: str = ""
    branch: str = Field(min_length=1, max_length=255)
    pushed_at: datetime | None = None
    commits: list[PushedCommit] = Field(max_length=500)
    client: str = ""


class PushResult(Camel):
    accepted: int
    duplicates: int


# ---- Commits (to the app) ----


class CommitOut(Camel):
    sha: str
    author_email: str
    author_name: str | None = None
    repo: str
    branch: str
    message: str
    #: Team-local 'YYYY-MM-DDTHH:mm'.
    timestamp: str
    files_changed: int
    url: str | None = None


# ---- Members ----


class MemberIn(Camel):
    name: str = Field(min_length=1, max_length=200)
    initials: str = Field(min_length=1, max_length=4)
    role: str = ""
    team: str = ""
    avatar_color: str = ""
    git_emails: list[str] = []


class MemberOut(MemberIn):
    id: str


# ---- Standup plans ----


class PlanItem(Camel):
    text: str = Field(min_length=1, max_length=500)
    #: manual = typed, suggested = from git activity, carried = unfinished item from the previous plan.
    source: Literal["manual", "suggested", "carried"] = "manual"
    #: Set by the owner when reviewing it the next day; unset means auto-detect from commits.
    #: Left out of the JSON while unset: the app's `done?: boolean` tells "auto" from "owner said no" by its absence.
    done: bool | None = Field(default=None, exclude_if=lambda done: done is None)


class Reviewed(Camel):
    yesterday: bool = False
    blockers: bool = False


class DayPlanIn(Camel):
    notes: list[str] = []
    today: list[PlanItem] = []
    blockers: list[str] = []
    resolved_blockers: list[str] = []
    reviewed: Reviewed = Reviewed()
    #: 'HH:mm' when submitted, null while still a draft.
    submitted_at: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class DayPlanOut(DayPlanIn):
    member_id: str
    date: date


# ---- Login ----


class LogIn(Camel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class SignUp(LogIn):
    """`email` is one of the member's git emails; they log in with it from then on."""

    password: str = Field(min_length=8, max_length=200)
