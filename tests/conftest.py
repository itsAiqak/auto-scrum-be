import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def make_client(tmp_path):
    """A client on a fresh SQLite file. Use it as a context manager: entering runs startup (tables + seed)."""

    def make(**overrides) -> TestClient:
        settings = Settings(**{"database_url": f"sqlite:///{tmp_path / 'test.db'}", "mock_commits_file": None, **overrides})
        return TestClient(create_app(settings))

    return make


@pytest.fixture
def client(make_client):
    """Logged in as Haiqal."""
    with make_client() as client:
        yield sign_up(client)


HAIQAL = "haiqal.hazhari@tmrnd.com.my"
PASSWORD = "correct horse battery"


def sign_up(client: TestClient, email: str = HAIQAL, password: str = PASSWORD) -> TestClient:
    """Signs up the team member with this git email, which also logs them in (the client keeps the cookie)."""
    response = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return client


def log_in(client: TestClient, email: str = HAIQAL, password: str = PASSWORD) -> TestClient:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


def push(sha: str = "a" * 40, *, branch: str = "preprod", repo: str = "intt-portal", timestamp: str = "2026-10-30T10:58:12+08:00",
         remote: str = "https://gitlab.tmrnd.com.my/intt/intt-portal.git", message: str = "fix preprod pipeline",
         email: str = "haiqal.hazhari@tmrnd.com.my", commits: list[dict] | None = None) -> dict:
    """A push body as Ascrum sends it."""
    return {
        "pusher": {"name": "Muhammad Haiqal bin Hazhari", "email": email},
        "repo": repo,
        "remoteUrl": remote,
        "branch": branch,
        "pushedAt": "2026-10-30T02:59:00.000Z",
        "commits": commits if commits is not None else [
            {"sha": sha, "authorEmail": email, "authorName": "Muhammad Haiqal bin Hazhari", "message": message, "timestamp": timestamp, "filesChanged": 1}
        ],
        "client": "ascrum-vscode/0.2.0",
    }
