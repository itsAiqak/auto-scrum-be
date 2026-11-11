"""First-run data: the app's team, and pushes stored by the old Node mock API."""

import json
import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .db import Commit, Member
from .times import to_db

log = logging.getLogger("uvicorn.error")

# Same team as the app's dummy data (src/app/core/data/standup.mock.ts), so commits match the members the app shows.
DEFAULT_MEMBERS = [
    dict(id="haiqal", name="Haiqal", initials="HQ", role="Frontend Developer", team="Frontend", avatar_color="#7050e8",
         git_emails=["haiqal@example.com", "haiqal.hazhari@tmrnd.com.my"]),
    dict(id="aina", name="Aina Rahman", initials="AR", role="Backend Developer", team="Backend", avatar_color="#dc1bb9",
         git_emails=["aina@example.com"]),
    dict(id="farid", name="Farid Ismail", initials="FI", role="Backend Developer", team="Backend", avatar_color="#3534df",
         git_emails=["farid@example.com"]),
    dict(id="meiling", name="Mei Ling Tan", initials="ML", role="Frontend Developer", team="Frontend", avatar_color="#277d78",
         git_emails=["meiling@example.com"]),
]


def seed(session: Session, settings: Settings) -> None:
    """Fills an empty database. Tables that already have rows are left alone."""
    if not session.scalar(select(func.count()).select_from(Member)):
        # New objects every time: ORM instances stay tied to the session (and database) they were first saved in.
        session.add_all(Member(**member) for member in DEFAULT_MEMBERS)
        log.info("Added %d team members", len(DEFAULT_MEMBERS))

    source = settings.mock_commits_file
    if source and source.is_file() and not session.scalar(select(func.count()).select_from(Commit)):
        imported = [_from_mock(item, settings) for item in json.loads(source.read_text(encoding="utf-8"))]
        session.add_all(imported)
        log.info("Imported %d commits from %s", len(imported), source)
    session.commit()


def _from_mock(item: dict, settings: Settings) -> Commit:
    return Commit(
        sha=item["sha"].lower(),
        author_email=item.get("authorEmail", ""),
        author_name=item.get("authorName"),
        repo=item["repo"],
        branch=item["branch"],
        message=item.get("message", ""),
        # The mock API stored team-local 'YYYY-MM-DDTHH:mm'.
        committed_at=to_db(datetime.fromisoformat(item["timestamp"]), settings.timezone),
        files_changed=int(item.get("filesChanged", 0)),
        url=item.get("url"),
    )
