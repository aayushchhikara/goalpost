from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_plan_a_week_complete_things_and_fill_the_backlog(client: TestClient, clock: Any) -> None:
    # A one-off idea goes to the backlog.
    resp = client.post(f"{API}/tasks", json={"title": "Write CONTRIBUTING guide"})
    assert resp.status_code == 201
    idea = resp.json()["task"]
    assert idea["in_backlog"] is True
    assert [i["task"]["id"] for i in client.get(f"{API}/backlog").json()["items"]] == [idea["id"]]

    # A recurring task, then plan the week with the backlog item as "any day".
    leetcode = client.post(
        f"{API}/tasks",
        json={"title": "LeetCode daily", "kind": "recurring", "recurrence_days": [0, 1, 2, 3, 5]},
    ).json()["task"]
    assert leetcode["recurrence_days"] == [0, 1, 2, 3, 5]
    week = client.post(
        f"{API}/weeks/2026-10-26/plan", json={"items": [{"task_id": idea["id"]}]}
    ).json()
    assert week["iso_week"] == 44 and week["status"] == "active"
    assert [len(d["occurrences"]) for d in week["days"]] == [1, 1, 1, 1, 0, 1, 0]
    assert [o["task"]["id"] for o in week["any_day"]] == [idea["id"]]
    assert week["summary"]["planned"] == 6
    assert client.get(f"{API}/backlog").json()["items"] == []

    # Today shows Monday's LeetCode; complete it.
    today = client.get(f"{API}/today").json()
    assert today["date"] == "2026-10-26"
    monday = today["items"][0]
    done = client.post(f"{API}/occurrences/{monday['id']}/complete").json()
    assert (done["status"], done["late"]) == ("done", False)
    assert done["completed_at"].startswith("2026-10-26T09:00:00")

    # The week ends with the one-off unfinished: it goes back to the backlog.
    clock.now = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    closed = client.post(f"{API}/jobs/close").json()
    assert closed["closed_weeks"] == ["2026-10-26"]
    assert closed["returned_to_backlog"] == 1
    backlog = client.get(f"{API}/backlog").json()["items"]
    assert [(i["task"]["id"], i["last_planned_week_start"]) for i in backlog] == [
        (idea["id"], "2026-10-26")
    ]

    adherence = client.get(f"{API}/weeks/2026-10-26").json()["adherence"]
    assert [(a["title"], a["done"], a["planned"], a["missed"]) for a in adherence] == [
        ("LeetCode daily", 1, 5, 4)
    ]


def test_task_drawer_edit_and_drop(client: TestClient) -> None:
    created = client.post(
        f"{API}/tasks",
        json={
            "title": "Groceries",
            "priority": "low",
            "plan": {"week_start": "2026-10-26", "date": "2026-10-28"},
        },
    ).json()
    task_id = created["task"]["id"]
    assert created["current_occurrence"]["date"] == "2026-10-28"
    assert created["task"]["first_planned_week_start"] == "2026-10-26"

    edited = client.patch(f"{API}/tasks/{task_id}", json={"title": "Groceries and laundry"}).json()
    assert (edited["task"]["title"], edited["task"]["priority"]) == ("Groceries and laundry", "low")

    moved = client.patch(
        f"{API}/occurrences/{created['current_occurrence']['id']}", json={"date": None}
    ).json()
    assert moved["date"] is None

    dropped = client.post(f"{API}/tasks/{task_id}/drop").json()
    assert dropped["task"]["status"] == "dropped"
    assert dropped["history"] == []  # nothing had happened yet, so nothing is kept


def test_errors_share_one_shape(client: TestClient) -> None:
    missing = client.get(f"{API}/tasks/01JUNKJUNKJUNKJUNKJUNKJUNK")
    assert missing.status_code == 404
    assert missing.json() == {
        "code": "not_found",
        "message": "Task 01JUNKJUNKJUNKJUNKJUNKJUNK not found",
        "details": [],
    }

    invalid = client.post(f"{API}/tasks", json={"title": "Gym", "kind": "recurring"})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"
    assert "recurrence day" in invalid.json()["details"][0]["message"]

    not_monday = client.get(f"{API}/weeks/2026-10-27")
    assert not_monday.status_code == 422
    assert not_monday.json()["details"] == [
        {
            "field": "monday",
            "message": "2026-10-27 is not a Monday; weeks are addressed by their Monday",
        }
    ]

    task = client.post(
        f"{API}/tasks", json={"title": "Read DP chapter 4", "plan": {"week_start": "2026-10-26"}}
    ).json()
    occurrence_id = task["current_occurrence"]["id"]
    assert client.post(f"{API}/occurrences/{occurrence_id}/complete").status_code == 200
    again = client.post(f"{API}/occurrences/{occurrence_id}/complete")
    assert again.status_code == 409
    assert again.json()["code"] == "already_done"

    unknown_route = client.get(f"{API}/nowhere")
    assert unknown_route.status_code == 404
    assert unknown_route.json()["code"] == "not_found"


def test_openapi_documents_the_error_shape(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/tasks"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert "HTTPValidationError" not in spec["components"]["schemas"]
