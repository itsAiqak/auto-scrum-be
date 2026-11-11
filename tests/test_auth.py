"""Login: team members sign up once with a git email, then log in. The session cookie guards reads; pushes keep the API token."""

from datetime import datetime

from sqlalchemy import update

from app.db import LoginSession
from app.deps import SESSION_COOKIE
from app.security import hash_password, verify_password
from conftest import HAIQAL, PASSWORD, log_in, push, sign_up


def test_reads_need_a_login_but_health_and_pushes_do_not(make_client):
    with make_client() as client:
        for path in ("/api/commits", "/api/events", "/api/members", "/api/plans", "/api/auth/me"):
            assert client.get(path).status_code == 401, path
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/pushes", json=push()).status_code == 200  # Ascrum uses the API token (none set here)


def test_sign_up_logs_in_with_an_httponly_cookie(make_client):
    with make_client() as client:
        response = client.post("/api/auth/signup", json={"email": " Haiqal.Hazhari@TMRND.com.my ", "password": PASSWORD})
        assert response.status_code == 201
        assert response.json()["id"] == "haiqal"
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api" in cookie
        assert client.get("/api/auth/me").json()["name"] == "Haiqal"


def test_only_team_members_sign_up_and_only_once(make_client):
    with make_client() as client:
        assert client.post("/api/auth/signup", json={"email": "stranger@example.com", "password": PASSWORD}).status_code == 403
        assert client.post("/api/auth/signup", json={"email": "aina@example.com", "password": "short"}).status_code == 422
        sign_up(client, "aina@example.com")
        again = client.post("/api/auth/signup", json={"email": "aina@example.com", "password": PASSWORD})
        assert again.status_code == 409 and "Log in instead" in again.json()["detail"]


def test_log_in_and_out(make_client):
    with make_client() as client:
        sign_up(client)
        token = client.cookies.get(SESSION_COOKIE)
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        # The old cookie is dead on the server too, not just forgotten by the browser.
        client.cookies.set(SESSION_COOKIE, token)
        assert client.get("/api/auth/me").status_code == 401
        client.cookies.clear()

        assert client.post("/api/auth/login", json={"email": HAIQAL, "password": "wrong password"}).status_code == 401
        assert client.post("/api/auth/login", json={"email": "aina@example.com", "password": PASSWORD}).status_code == 401  # no account
        assert log_in(client).get("/api/auth/me").json()["id"] == "haiqal"


def test_expired_sessions_are_refused(client):
    with client.app.state.sessions() as session:
        session.execute(update(LoginSession).values(expires_at=datetime(2000, 1, 1)))
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_passwords_are_stored_salted_and_hashed():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    assert verify_password(PASSWORD, first) and not verify_password("wrong", first)
    assert not verify_password(PASSWORD, "not a hash")
