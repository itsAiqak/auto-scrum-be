from conftest import push, sign_up


def test_a_push_comes_back_as_app_commits(client):
    assert client.post("/api/pushes", json=push()).json() == {"accepted": 1, "duplicates": 0}
    assert client.get("/api/commits").json() == [
        {
            "sha": "a" * 40,
            "authorEmail": "haiqal.hazhari@tmrnd.com.my",
            "authorName": "Muhammad Haiqal bin Hazhari",
            "repo": "intt-portal",
            "branch": "preprod",
            "message": "fix preprod pipeline",
            "timestamp": "2026-10-30T10:58",
            "filesChanged": 1,
            "url": f"https://gitlab.tmrnd.com.my/intt/intt-portal/-/commit/{'a' * 40}",
        }
    ]


def test_times_are_shown_in_the_team_time_zone(client):
    # 23:30 UTC is 07:30 the next morning in Kuala Lumpur.
    client.post("/api/pushes", json=push(timestamp="2026-10-29T23:30:00Z"))
    assert client.get("/api/commits").json()[0]["timestamp"] == "2026-10-30T07:30"


def test_the_same_commit_twice_is_a_duplicate(client):
    client.post("/api/pushes", json=push())
    assert client.post("/api/pushes", json=push(sha="A" * 40)).json() == {"accepted": 0, "duplicates": 1}
    assert len(client.get("/api/commits").json()) == 1


def test_commits_without_a_web_remote_get_links_on_the_repos_next_push(client):
    client.post("/api/pushes", json=push("b" * 40, remote="C:/repos/intt-portal.git"))
    assert "url" not in client.get("/api/commits").json()[0]
    client.post("/api/pushes", json=push("c" * 40, timestamp="2026-10-30T11:30:00+08:00"))
    assert [c["url"].rsplit("/", 1)[1] for c in client.get("/api/commits").json()] == ["b" * 40, "c" * 40]


def test_bad_pushes_are_rejected(client):
    assert client.post("/api/pushes", json=push(sha="not-a-sha")).status_code == 422
    assert client.post("/api/pushes", json={**push(), "repo": ""}).status_code == 422
    assert client.post("/api/pushes", json={**push(), "commits": "nope"}).status_code == 422


def test_commit_filters(client):
    client.post("/api/pushes", json=push("1" * 40, timestamp="2026-10-28T09:00:00+08:00"))
    client.post("/api/pushes", json=push("2" * 40, timestamp="2026-10-29T23:59:00+08:00", repo="auto-scrum"))
    client.post("/api/pushes", json=push("3" * 40, timestamp="2026-10-30T00:01:00+08:00", email="aina@example.com"))
    shas = lambda query: [c["sha"][0] for c in client.get(f"/api/commits?{query}").json()]  # noqa: E731
    assert shas("since=2026-10-29") == ["2", "3"]
    assert shas("until=2026-10-29") == ["1", "2"]
    assert shas("since=2026-10-29&until=2026-10-29") == ["2"]
    assert shas("author=AINA@example.com") == ["3"]
    assert shas("repo=auto-scrum") == ["2"]


def test_writes_need_the_token_when_one_is_set(make_client):
    with make_client(api_token="s3cret") as client:
        assert client.post("/api/pushes", json=push()).status_code == 401
        assert client.post("/api/pushes", json=push(), headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.post("/api/pushes", json=push(), headers={"Authorization": "Bearer s3cret"}).status_code == 200
        # Reads don't take the token: they need a login.
        assert client.get("/api/commits", headers={"Authorization": "Bearer s3cret"}).status_code == 401
        assert sign_up(client).get("/api/commits").status_code == 200


def test_health(client):
    client.post("/api/pushes", json=push())
    assert client.get("/api/health").json() == {"ok": True, "commits": 1, "members": 4, "liveListeners": 0}
