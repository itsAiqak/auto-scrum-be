import re

from conftest import sign_up

PLAN = {
    "notes": ["Sprint planning (2h)"],
    "today": [{"text": "Add date navigation", "source": "manual"}, {"text": "Respond to review on PR #12", "source": "suggested", "done": True}],
    "blockers": ["Waiting for design review"],
    "resolvedBlockers": [],
    "reviewed": {"yesterday": True, "blockers": False},
    "submittedAt": None,
}


def test_the_team_is_seeded_with_git_emails(client):
    members = client.get("/api/members").json()
    assert [m["id"] for m in members] == ["aina", "farid", "haiqal", "meiling"]  # by team, then name
    haiqal = client.get("/api/members/haiqal").json()
    assert haiqal["gitEmails"] == ["haiqal@example.com", "haiqal.hazhari@tmrnd.com.my"]
    assert haiqal["avatarColor"] == "#7050e8"


def test_add_and_change_a_member(client):
    body = {"name": "Siti Aminah", "initials": "SA", "role": "QA", "team": "Frontend", "gitEmails": [" siti@example.com ", ""]}
    assert client.put("/api/members/siti", json=body).json()["gitEmails"] == ["siti@example.com"]
    assert client.put("/api/members/siti", json={**body, "role": "QA Lead"}).json()["role"] == "QA Lead"
    assert client.get("/api/members/nobody").status_code == 404
    assert client.put("/api/members/Not Valid", json=body).status_code == 422


def test_save_and_read_a_plan(client):
    saved = client.put("/api/plans/haiqal/2026-10-30", json=PLAN).json()
    # Unset `done` stays out of the JSON (not null), so the app still auto-detects it.
    assert saved == {**PLAN, "memberId": "haiqal", "date": "2026-10-30"}
    assert client.get("/api/plans/haiqal/2026-10-30").json() == saved
    # Saving again replaces the whole plan.
    assert client.put("/api/plans/haiqal/2026-10-30", json={**PLAN, "blockers": []}).json()["blockers"] == []


def test_list_plans_by_day_or_member(client):
    client.put("/api/plans/haiqal/2026-10-29", json=PLAN)
    client.put("/api/plans/haiqal/2026-10-30", json=PLAN)
    sign_up(client, "aina@example.com").put("/api/plans/aina/2026-10-30", json=PLAN)
    pairs = lambda query: [(p["memberId"], p["date"]) for p in client.get(f"/api/plans?{query}").json()]  # noqa: E731
    assert pairs("date=2026-10-30") == [("aina", "2026-10-30"), ("haiqal", "2026-10-30")]
    assert pairs("memberId=haiqal") == [("haiqal", "2026-10-29"), ("haiqal", "2026-10-30")]
    assert pairs("memberId=haiqal&since=2026-10-30") == [("haiqal", "2026-10-30")]


def test_submit_stamps_the_time_once(client):
    first = client.post("/api/plans/haiqal/2026-10-30/submit").json()
    assert re.fullmatch(r"\d{2}:\d{2}", first["submittedAt"])
    assert first["today"] == [] and first["reviewed"] == {"yesterday": False, "blockers": False}
    client.put("/api/plans/haiqal/2026-10-30", json={**PLAN, "submittedAt": "08:55"})
    assert client.post("/api/plans/haiqal/2026-10-30/submit").json()["submittedAt"] == "08:55"


def test_members_change_only_their_own_plan_but_see_everyones(client):
    assert client.put("/api/plans/aina/2026-10-30", json=PLAN).status_code == 403
    assert client.post("/api/plans/aina/2026-10-30/submit").status_code == 403
    client.put("/api/plans/haiqal/2026-10-30", json=PLAN)
    sign_up(client, "aina@example.com")
    assert client.get("/api/plans/haiqal/2026-10-30").json()["blockers"] == PLAN["blockers"]
    assert client.put("/api/plans/haiqal/2026-10-30", json=PLAN).status_code == 403


def test_plan_mistakes(client):
    assert client.get("/api/plans/haiqal/2026-10-30").status_code == 404
    assert client.put("/api/plans/nobody/2026-10-30", json=PLAN).status_code == 403  # not your plan
    assert client.put("/api/plans/haiqal/30-10-2026", json=PLAN).status_code == 422
    assert client.put("/api/plans/haiqal/2026-10-30", json={**PLAN, "submittedAt": "9am"}).status_code == 422
    assert client.put("/api/plans/haiqal/2026-10-30", json={**PLAN, "today": [{"text": "x", "source": "magic"}]}).status_code == 422
