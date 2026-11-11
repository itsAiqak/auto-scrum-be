import json

import pytest

from app.links import commit_url
from conftest import log_in, sign_up

SHA = "abc123"


@pytest.mark.parametrize(
    ("remote", "url"),
    [
        ("https://gitlab.tmrnd.com.my/intt/intt-portal.git", "https://gitlab.tmrnd.com.my/intt/intt-portal/-/commit/abc123"),
        ("git@gitlab.tmrnd.com.my:intt/intt-portal.git", "https://gitlab.tmrnd.com.my/intt/intt-portal/-/commit/abc123"),
        ("ssh://git@gitlab.example.com:2222/group/sub/repo.git", "https://gitlab.example.com/group/sub/repo/-/commit/abc123"),
        ("http://gitlab.local.lan/team/app", "http://gitlab.local.lan/team/app/-/commit/abc123"),
        ("https://github.com/antrix/auto-scrum.git", "https://github.com/antrix/auto-scrum/commit/abc123"),
        ("git@github.com:antrix/auto-scrum.git", "https://github.com/antrix/auto-scrum/commit/abc123"),
        ("https://dev.azure.com/org/proj/_git/payment-service", "https://dev.azure.com/org/proj/_git/payment-service/commit/abc123"),
        ("https://bitbucket.org/team/repo.git", "https://bitbucket.org/team/repo/commits/abc123"),
        ("C:/Users/me/repos/x.git", None),
        ("C:\\repos\\x", None),
        ("/home/me/x.git", None),
        ("", None),
    ],
)
def test_commit_url(remote, url):
    assert commit_url(remote, SHA) == url


def test_pushes_from_the_node_mock_api_are_imported_once(make_client, tmp_path):
    old = tmp_path / "commits.json"
    old.write_text(json.dumps([{"sha": "D" * 40, "authorEmail": "haiqal.hazhari@tmrnd.com.my", "repo": "intt-portal", "branch": "development",
                                 "message": "support page, rename header", "timestamp": "2026-10-30T10:50", "filesChanged": 1}]))
    with make_client(mock_commits_file=old) as client:
        assert [(c["sha"], c["timestamp"]) for c in sign_up(client).get("/api/commits").json()] == [("d" * 40, "2026-10-30T10:50")]
    old.write_text("[]")
    with make_client(mock_commits_file=old) as client:  # same database: not imported again, nothing lost
        assert len(log_in(client).get("/api/commits").json()) == 1
