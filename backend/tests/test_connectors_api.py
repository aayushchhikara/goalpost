from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from goalpost import sdk
from goalpost.main import app
from goalpost.sdk.loader import Registry
from goalpost.services.connectors import installed_connectors
from pydantic import BaseModel, Field

API = "/api/v1"


class ProfileConfig(BaseModel):
    username: str = Field(min_length=1)


class Solve(BaseModel):
    problem: str


class Fake(sdk.Connector[ProfileConfig]):
    manifest = sdk.Manifest(
        id="fake",
        name="Fake Judge",
        version="1.0.0",
        sdk_version=sdk.SDK_VERSION,
        description="For tests",
        config=ProfileConfig,
        secrets=["FAKE_JUDGE_TOKEN"],
        event_kinds=[sdk.EventKind(name="solve", payload=Solve, rule_fields=["problem"])],
    )
    script: list[sdk.FetchResult | Exception] = []

    def test_connection(self, config: ProfileConfig, secrets: Mapping[str, str]) -> str:
        if config.username == "nobody":
            raise sdk.ConnectorError("No such user")
        return f"Hello {config.username}"

    def fetch(
        self, config: ProfileConfig, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> sdk.FetchResult:
        outcome = Fake.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def solves(*ids: str) -> sdk.FetchResult:
    at = datetime(2026, 10, 26, 18, 20, tzinfo=UTC)
    events = [
        sdk.Event(source_id=i, kind="solve", occurred_at=at, payload={"problem": i}) for i in ids
    ]
    return sdk.FetchResult(events=events, cursor={"seen": list(ids)})


@pytest.fixture(autouse=True)
def fake_registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    Fake.script = []
    monkeypatch.setenv("FAKE_JUDGE_TOKEN", "secret")
    app.dependency_overrides[installed_connectors] = lambda: Registry(types={"fake": Fake})
    yield
    app.dependency_overrides.pop(installed_connectors, None)


def add_connector(client: TestClient, username: str = "me") -> dict[str, Any]:
    resp = client.post(f"{API}/connectors", json={"type": "fake", "config": {"username": username}})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def test_connector_types_describe_installed_manifests(client: TestClient) -> None:
    body = client.get(f"{API}/connector-types").json()
    assert body["load_errors"] == []
    [fake] = body["items"]
    assert (fake["id"], fake["name"], fake["auth"]) == ("fake", "Fake Judge", "none")
    assert fake["config_schema"]["required"] == ["username"]
    assert fake["secrets"] == [{"name": "FAKE_JUDGE_TOKEN", "present": True}]
    assert fake["event_kinds"][0]["rule_fields"] == ["problem"]
    assert fake["event_kinds"][0]["payload_schema"]["properties"]["problem"]["type"] == "string"
    assert fake["min_sync_interval_minutes"] == 60


def test_creating_connectors_validates_type_and_config(client: TestClient) -> None:
    created = add_connector(client)
    assert created["name"] == "Fake Judge"
    assert created["config"] == {"username": "me"}
    assert (created["status"], created["last_run"], created["enabled"]) == (
        "never_synced",
        None,
        True,
    )

    unknown = client.post(f"{API}/connectors", json={"type": "nope", "config": {}})
    assert unknown.status_code == 422
    assert unknown.json()["details"][0]["field"] == "type"

    bad = client.post(f"{API}/connectors", json={"type": "fake", "config": {"username": ""}})
    assert bad.status_code == 422
    assert bad.json()["details"][0]["field"] == "config.username"

    assert [c["id"] for c in client.get(f"{API}/connectors").json()["items"]] == [created["id"]]


def test_the_test_button_reports_success_and_failure(client: TestClient) -> None:
    good = add_connector(client)
    assert client.post(f"{API}/connectors/{good['id']}/test").json() == {
        "ok": True,
        "message": "Hello me",
    }
    bad = add_connector(client, "nobody")
    resp = client.post(f"{API}/connectors/{bad['id']}/test")
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "message": "No such user"}
    assert client.post(f"{API}/connectors/01NOPE00000000000000000000/test").status_code == 404


def test_sync_now_runs_in_the_background_and_dedupes(client: TestClient) -> None:
    connector = add_connector(client)
    Fake.script = [solves("a", "b"), solves("b")]

    first = client.post(f"{API}/sync", json={})
    assert first.status_code == 202
    assert first.json() == {"connector_ids": [connector["id"]]}

    # TestClient finishes background tasks before returning, so the run is already recorded.
    runs = client.get(f"{API}/sync/runs").json()["items"]
    assert [(r["trigger"], r["status"], r["events_added"]) for r in runs] == [("manual", "ok", 2)]

    client.post(f"{API}/sync", json={"connector_id": connector["id"]})
    runs = client.get(f"{API}/sync/runs").json()["items"]
    assert [r["events_added"] for r in runs] == [0, 2]  # newest first; nothing new the second time

    view = client.get(f"{API}/connectors").json()["items"][0]
    assert view["status"] == "ok"
    assert view["last_success_at"] is not None


def test_status_summarises_syncs_and_problems(client: TestClient) -> None:
    empty = client.get(f"{API}/status").json()
    assert empty == {
        "inbox_count": 0,
        "backlog_count": 0,
        "syncing": False,
        "last_sync_at": None,
        "next_sync_at": None,
        "connector_errors": [],
    }

    connector = add_connector(client)
    client.post(f"{API}/tasks", json={"title": "Idea"})
    Fake.script = [solves("a"), sdk.AuthError("Token revoked")]
    client.post(f"{API}/sync", json={})
    ok = client.get(f"{API}/status").json()
    assert ok["backlog_count"] == 1
    assert ok["last_sync_at"] is not None

    client.post(f"{API}/sync", json={})
    status = client.get(f"{API}/status").json()
    assert status["connector_errors"] == [
        {
            "connector_id": connector["id"],
            "name": "Fake Judge",
            "message": "Token revoked",
            "paused": True,
        }
    ]
    view = client.get(f"{API}/connectors").json()["items"][0]
    assert (view["status"], view["pause_reason"]) == ("paused", "Token revoked")

    # A passing test lifts the pause.
    assert client.post(f"{API}/connectors/{connector['id']}/test").json()["ok"] is True
    assert client.get(f"{API}/connectors").json()["items"][0]["status"] == "failing"
    assert client.get(f"{API}/status").json()["connector_errors"][0]["paused"] is False


def test_sync_runs_page_with_before(client: TestClient) -> None:
    add_connector(client)
    Fake.script = [solves(str(i)) for i in range(5)]
    for _ in range(5):
        client.post(f"{API}/sync", json={})
    page1 = client.get(f"{API}/sync/runs", params={"limit": 2}).json()
    page2 = client.get(
        f"{API}/sync/runs", params={"limit": 2, "before": page1["next_before"]}
    ).json()
    page3 = client.get(
        f"{API}/sync/runs", params={"limit": 2, "before": page2["next_before"]}
    ).json()
    ids = [r["id"] for p in (page1, page2, page3) for r in p["items"]]
    assert len(ids) == len(set(ids)) == 5
    assert ids == sorted(ids, reverse=True)
    assert page3["next_before"] is None


def test_syncing_an_unknown_connector_is_404(client: TestClient) -> None:
    resp = client.post(f"{API}/sync", json={"connector_id": "01NOPE00000000000000000000"})
    assert resp.status_code == 404
