"""The push feed: Ascrum posts pushes, the app reads the commits and listens for new ones."""

import logging
from collections.abc import AsyncIterable
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import TypeAdapter
from sqlalchemy import func, select

from ..db import Commit, Push
from ..deps import Authorized, BrokerDep, LoggedIn, SessionDep, SettingsDep
from ..links import commit_url
from ..schemas import CommitOut, PushIn, PushResult
from ..times import day_start, local_minute, now_utc, to_db

router = APIRouter(tags=["push feed"])
log = logging.getLogger("uvicorn.error")
_commit_list = TypeAdapter(list[CommitOut])


def commit_out(commit: Commit, tz: ZoneInfo) -> CommitOut:
    return CommitOut(
        sha=commit.sha,
        author_email=commit.author_email,
        author_name=commit.author_name,
        repo=commit.repo,
        branch=commit.branch,
        message=commit.message,
        timestamp=local_minute(commit.committed_at, tz),
        files_changed=commit.files_changed,
        url=commit.url,
    )


@router.post("/pushes", response_model=PushResult, dependencies=[Authorized])
def receive_push(push: PushIn, session: SessionDep, settings: SettingsDep, broker: BrokerDep) -> PushResult:
    """One push to one branch, from Ascrum. Commits are deduped by sha, so retries and pushes from other machines are harmless."""
    tz = settings.timezone
    incoming = {c.sha.lower(): c for c in push.commits}
    known = set(session.scalars(select(Commit.sha).where(Commit.sha.in_(incoming))))
    record = Push(
        pusher_name=push.pusher.name,
        pusher_email=push.pusher.email,
        repo=push.repo,
        branch=push.branch,
        remote_url=push.remote_url,
        pushed_at=to_db(push.pushed_at, tz) if push.pushed_at else None,
        received_at=now_utc(),
        client=push.client,
    )
    session.add(record)
    added = [
        Commit(
            sha=sha,
            push=record,
            author_email=c.author_email,
            author_name=c.author_name or None,
            repo=push.repo,
            branch=push.branch,
            message=c.message,
            committed_at=to_db(c.timestamp, tz),
            files_changed=c.files_changed,
            url=commit_url(push.remote_url, sha),
        )
        for sha, c in incoming.items()
        if sha not in known
    ]
    # Explicitly: SQLAlchemy 2 doesn't cascade objects into the session through the `push=` backref.
    session.add_all(added)

    # Commits stored before the repo's remote was known (e.g. imported) get their links now.
    linked: list[Commit] = []
    if commit_url(push.remote_url, "0"):
        linked = list(session.scalars(select(Commit).where(Commit.repo == push.repo, Commit.url.is_(None))))
        for commit in linked:
            commit.url = commit_url(push.remote_url, commit.sha)
    session.commit()

    changed = [commit_out(c, tz) for c in [*linked, *added]]
    if changed:
        broker.publish("commits", _commit_list.dump_json(changed, by_alias=True, exclude_none=True).decode())
    log.info("%s pushed %d commit(s) to %s/%s (%d new)", push.pusher.name or push.pusher.email or "someone", len(push.commits), push.repo, push.branch, len(added))
    return PushResult(accepted=len(added), duplicates=len(push.commits) - len(added))


@router.get("/commits", response_model=list[CommitOut], response_model_exclude_none=True, dependencies=[LoggedIn])
def list_commits(
    session: SessionDep,
    settings: SettingsDep,
    since: date | None = None,
    until: date | None = None,
    author: str | None = None,
    repo: str | None = None,
) -> list[CommitOut]:
    """Pushed commits, oldest first, in the app's `Commit` shape. `since`/`until` are team-local days (inclusive), `author` an email."""
    tz = settings.timezone
    query = select(Commit).order_by(Commit.committed_at)
    if since:
        query = query.where(Commit.committed_at >= day_start(since, tz))
    if until:
        query = query.where(Commit.committed_at < day_start(until + timedelta(days=1), tz))
    if author:
        query = query.where(func.lower(Commit.author_email) == author.lower())
    if repo:
        query = query.where(Commit.repo == repo)
    return [commit_out(c, tz) for c in session.scalars(query)]


@router.get("/events", response_class=EventSourceResponse, dependencies=[LoggedIn])
async def events(broker: BrokerDep) -> AsyncIterable[ServerSentEvent]:
    """Live feed for the app: a `commits` event with new or updated commits after each push. FastAPI pings every 15 s."""
    queue = broker.subscribe()
    try:
        yield ServerSentEvent(comment="connected")
        while True:
            event, data = await queue.get()
            yield ServerSentEvent(event=event, raw_data=data)
    finally:
        broker.unsubscribe(queue)
