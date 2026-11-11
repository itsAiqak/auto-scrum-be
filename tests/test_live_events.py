"""The live feed against a real uvicorn server: open /api/events like the app's EventSource, push, receive the commits."""

import json
import socket
import threading
import time

import httpx2
import uvicorn

from app.config import Settings
from app.main import create_app
from conftest import HAIQAL, PASSWORD, push


def test_a_push_reaches_open_event_streams(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'live.db'}", mock_commits_file=None))
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning", timeout_graceful_shutdown=1))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/api"
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        with httpx2.Client(timeout=5) as http:
            # Like the browser: log in, then the session cookie goes along with the stream request.
            assert http.post(f"{base}/auth/signup", json={"email": HAIQAL, "password": PASSWORD}).status_code == 201
            stream_events(http, base)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def stream_events(http: httpx2.Client, base: str) -> None:
    with http.stream("GET", f"{base}/events", headers={"Origin": "http://localhost:4300"}) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["access-control-allow-origin"] == "http://localhost:4300"
        assert stream.headers["access-control-allow-credentials"] == "true"
        lines = stream.iter_lines()
        assert next(lines) == ": connected"
        assert http.get(f"{base}/health").json()["liveListeners"] == 1
        http.post(f"{base}/pushes", json=push())
        event = [next(lines) for _ in range(3)]
    assert event[0] == ""  # end of the 'connected' comment block
    assert event[1] == "event: commits"
    data = json.loads(event[2].removeprefix("data: "))
    assert [(c["sha"], c["timestamp"], c["branch"]) for c in data] == [("a" * 40, "2026-10-30T10:58", "preprod")]
