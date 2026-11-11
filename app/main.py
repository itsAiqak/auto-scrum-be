"""Auto-Scrum API.

Run:  uv run uvicorn app.main:app --port 4310 --reload   (or `npm run api` from auto-scrum)
Docs: http://localhost:4310/docs
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from .config import Settings, load_settings
from .db import Base, Commit, Member, make_engine
from .deps import BrokerDep, SessionDep
from .events import EventBroker
from .routes import auth, feed, members, plans
from .seed import seed

DESCRIPTION = """
Backend for **Auto-Scrum**, the automatic daily standup.

* **Push feed**: the Ascrum VS Code extension posts each push (`POST /api/pushes`); the app reads the
  commits (`GET /api/commits`) and gets new ones live (`GET /api/events`).
* **Members**: the team, matched to commits by their git emails.
* **Standup plans**: what each member plans for the day, their blockers, and when they submitted.
* **Login**: team members sign up once with one of their git emails (`POST /api/auth/signup`), then log in
  with email and password. A session cookie keeps them logged in for 30 days.

Commits, events, members and plans need a login; members can only change their own plan.
Pushes and member edits need `Authorization: Bearer <API_TOKEN>` when the server has an `API_TOKEN`.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    broker = EventBroker()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(engine)
        with sessions() as session:
            seed(session, settings)
        broker.bind(asyncio.get_running_loop())
        yield
        engine.dispose()

    app = FastAPI(title="Auto-Scrum API", version="0.1.0", description=DESCRIPTION, lifespan=lifespan)
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.broker = broker
    # Credentials: the app sends its login cookie with every request.
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/api/health", tags=["health"])
    def health(session: SessionDep, events: BrokerDep) -> dict[str, int | bool]:
        return {
            "ok": True,
            "commits": session.scalar(select(func.count()).select_from(Commit)) or 0,
            "members": session.scalar(select(func.count()).select_from(Member)) or 0,
            "liveListeners": events.listeners,
        }

    for router in (auth.router, feed.router, members.router, plans.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
