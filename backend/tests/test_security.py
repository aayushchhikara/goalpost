import pytest
from fastapi.testclient import TestClient
from goalpost.security import _hostname

API = "/api/v1"
FRONTEND = "http://localhost:3000"
EVIL = "https://evil.example"


def plan_this_week(client: TestClient) -> str:
    task = client.post(
        f"{API}/tasks", json={"title": "Auth cleanup", "plan": {"week_start": "2026-10-26"}}
    ).json()
    return task["task"]["id"]


# Cross-site writes


def test_cross_site_post_is_refused_and_has_no_effect(client: TestClient) -> None:
    plan_this_week(client)

    # What a malicious page can send with fetch(..., {method: "POST", mode: "no-cors"}).
    resp = client.post(f"{API}/jobs/close?as_of=2099-01-01", headers={"Origin": EVIL})
    assert resp.status_code == 403
    assert resp.json() == {
        "code": "forbidden_origin",
        "message": f"Requests from {EVIL} may not change data",
        "details": [],
    }
    assert client.get(f"{API}/weeks/2026-10-26").json()["status"] == "active"


@pytest.mark.parametrize("origin", [EVIL, "null", "http://localhost:3001", "http://127.0.0.1:3000"])
def test_every_write_method_refuses_foreign_origins(client: TestClient, origin: str) -> None:
    task_id = plan_this_week(client)
    headers = {"Origin": origin}
    assert client.post(f"{API}/tasks", json={"title": "x"}, headers=headers).status_code == 403
    assert (
        client.patch(f"{API}/tasks/{task_id}", json={"title": "x"}, headers=headers).status_code
        == 403
    )
    assert client.post(f"{API}/tasks/{task_id}/drop", headers=headers).status_code == 403
    assert client.delete(f"{API}/tasks/{task_id}", headers=headers).status_code == 403
    assert client.get(f"{API}/tasks/{task_id}").json()["task"]["title"] == "Auth cleanup"


def test_the_frontend_can_write(client: TestClient) -> None:
    resp = client.post(f"{API}/tasks", json={"title": "Groceries"}, headers={"Origin": FRONTEND})
    assert resp.status_code == 201
    assert resp.headers["access-control-allow-origin"] == FRONTEND
    trailing_slash = client.post(
        f"{API}/tasks", json={"title": "Laundry"}, headers={"Origin": FRONTEND + "/"}
    )
    assert trailing_slash.status_code == 201


def test_requests_without_an_origin_still_work(client: TestClient) -> None:
    # curl, scripts and server-side calls send no Origin; browsers always do cross-site.
    assert client.post(f"{API}/tasks", json={"title": "Groceries"}).status_code == 201
    assert client.post(f"{API}/jobs/close").status_code == 200


def test_reads_from_other_origins_are_not_shared(client: TestClient) -> None:
    resp = client.get(f"{API}/backlog", headers={"Origin": EVIL})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers  # the browser hides the body


def test_cors_preflight_still_answers_the_frontend(client: TestClient) -> None:
    resp = client.options(
        f"{API}/tasks",
        headers={"Origin": FRONTEND, "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == FRONTEND


# DNS rebinding


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "192.168.1.20:8000", ""])
def test_foreign_hosts_are_refused(client: TestClient, host: str) -> None:
    resp = client.get(f"{API}/backlog", headers={"Host": host})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_host"
    assert client.get("/health", headers={"Host": host}).status_code == 400


@pytest.mark.parametrize(
    "host", ["localhost", "localhost:8000", "127.0.0.1:8000", "LOCALHOST:8000"]
)
def test_local_hosts_are_served(client: TestClient, host: str) -> None:
    assert client.get(f"{API}/backlog", headers={"Host": host}).status_code == 200


def test_hostname_strips_ports() -> None:
    assert _hostname("localhost:8000") == "localhost"
    assert _hostname("[::1]:8000") == "::1"
    assert _hostname("Example.COM") == "example.com"
