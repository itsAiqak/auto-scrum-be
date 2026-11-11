"""Settings, read from environment variables so the same code runs locally and on a server."""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    #: SQLAlchemy URL. SQLite file by default; e.g. postgresql+psycopg://user:pass@host/autoscrum on a server.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'auto-scrum.db'}"
    #: When set, pushes and member edits need `Authorization: Bearer <token>`. Ascrum: "Set API Token".
    #: (People log in instead: reads and plans need a login.)
    api_token: str | None = None
    #: Login cookies only over HTTPS. Turn on when the API is served over HTTPS.
    secure_cookies: bool = False
    #: The team's time zone. The app shows commit times and standup dates in it.
    timezone: ZoneInfo = ZoneInfo("Asia/Kuala_Lumpur")
    cors_origins: tuple[str, ...] = ("http://localhost:4300", "http://localhost:4200")
    #: Pushes stored by the old Node mock API, imported once into an empty database.
    mock_commits_file: Path | None = BACKEND_DIR.parent / "mock-api" / "commits.json"


def load_settings() -> Settings:
    defaults = Settings()
    origins = os.getenv("CORS_ORIGINS")
    return Settings(
        database_url=os.getenv("DATABASE_URL", defaults.database_url),
        api_token=os.getenv("API_TOKEN") or None,
        secure_cookies=os.getenv("SECURE_COOKIES", "").lower() in ("1", "true", "yes"),
        timezone=ZoneInfo(os.getenv("TEAM_TIMEZONE", defaults.timezone.key)),
        cors_origins=tuple(o.strip() for o in origins.split(",")) if origins else defaults.cors_origins,
        mock_commits_file=defaults.mock_commits_file,
    )
