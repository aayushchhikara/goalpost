from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from goalpost import sdk
from goalpost.main import app
from goalpost.sdk.loader import Registry
from goalpost.services.connectors import installed_connectors
from goalpost.services.dates import local_date, week_monday
from pydantic import BaseModel

API = "/api/v1"
# Syncs run rules against the real clock, so this file runs the API on the real date too.
NOW = datetime.now(UTC)
TODAY = local_date(NOW, "UTC").isoformat()  # tests run with GOALPOST_TIMEZONE=UTC
MONDAY = week_monday(local_date(NOW, "UTC")).isoformat()


class Config(BaseModel):
    username: str = "me"


class Commit(BaseModel):
    repo: str
    message: str


class Git(sdk.Connector[Config]):
    manifest = sdk.Manifest(
        id="git",
        name="Git",
        version="1",
        sdk_version=sdk.SDK_VERSION,
        config=Config,
        event_kinds=[
            sdk.EventKind(
                name="commit",
                payload=Commit,
                rule_fields=["repo", "message"],
                title_field="message",
            )
        ],
    )
    script: list[sdk.FetchResult] = []

    def test_connection(self, config: Config, secrets: Mapping[str, str]) -> str:
        return "ok"

    def fetch(
        self, config: Config, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> sdk.FetchResult:
        return Git.script.pop(0)


def commits(*items: tuple[str, str]) -> sdk.FetchResult:
    at = NOW
    return sdk.FetchResult(
        events=[
            sdk.Event(
                source_id=sid,
                kind="commit",
                occurred_at=at,
                payload={"repo": "goalpost", "message": msg},
            )
            for sid, msg in items
        ],
        cursor=None,
    )


@pytest.fixture(autouse=True)
def registry(clock: Any) -> Iterator[None]:
    clock.now = NOW
    Git.script = []
    app.dependency_overrides[installed_connectors] = lambda: Registry(types={"git": Git})
    yield
    app.dependency_overrides.pop(installed_connectors, None)


def setup(client: TestClient) -> tuple[str, str]:
    connector = client.post(f"{API}/connectors", json={"type": "git", "config": {}}).json()["id"]
    task = client.post(
        f"{API}/tasks",
        json={"title": "Auth cleanup", "plan": {"week_start": MONDAY, "date": TODAY}},
    ).json()["task"]["id"]
    rule = client.put(
        f"{API}/tasks/{task}/rule",
        json={
            "connector_id": connector,
            "kind": "commit",
            "filters": [{"field": "repo", "op": "equals", "value": "goalpost"}],
        },
    )
    assert rule.status_code == 200, rule.json()
    assert rule.json()["connector_name"] == "Git"
    return connector, task


def test_rule_to_suggestion_to_evidence(client: TestClient) -> None:
    _, task = setup(client)
    Git.script = [commits(("c1", "feat: token refresh"))]
    client.post(f"{API}/sync", json={})

    [suggestion] = client.get(f"{API}/suggestions", params={"status": "pending"}).json()["items"]
    assert suggestion["occurrence"]["task"]["id"] == task
    assert [(e["title"], e["connector_name"]) for e in suggestion["events"]] == [
        ("feat: token refresh", "Git")
    ]
    assert suggestion["rule"]["filters"] == [{"field": "repo", "op": "equals", "value": "goalpost"}]
    assert client.get(f"{API}/status").json()["inbox_count"] == 1
    today = client.get(f"{API}/today").json()["items"][0]
    assert today["pending_suggestion_id"] == suggestion["id"]

    accepted = client.post(f"{API}/suggestions/{suggestion['id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["occurrence"]["status"] == "done"
    assert accepted.json()["occurrence"]["evidence_count"] == 1
    assert client.post(f"{API}/suggestions/{suggestion['id']}/accept").status_code == 409

    detail = client.get(f"{API}/tasks/{task}").json()
    assert [e["title"] for e in detail["evidence"]] == ["feat: token refresh"]
    assert detail["rule"]["kind"] == "commit"
    assert client.get(f"{API}/status").json()["inbox_count"] == 0


def test_reject_with_exclusion_then_remove_it(client: TestClient) -> None:
    _, task = setup(client)
    Git.script = [commits(("c1", "chore: bump"))]
    client.post(f"{API}/sync", json={})
    [suggestion] = client.get(f"{API}/suggestions").json()["items"]

    rejected = client.post(
        f"{API}/suggestions/{suggestion['id']}/reject",
        json={"exclusion": {"field": "message", "op": "regex", "value": "^chore:"}},
    ).json()
    assert rejected["status"] == "rejected"
    [exclusion] = client.get(f"{API}/tasks/{task}").json()["rule"]["exclusions"]
    assert exclusion["created_from_suggestion_id"] == suggestion["id"]

    bad = client.post(f"{API}/suggestions/{suggestion['id']}/reject", json={})
    assert bad.status_code == 409

    gone = client.delete(f"{API}/tasks/{task}/rule/exclusions/{exclusion['id']}")
    assert gone.status_code == 204
    assert client.get(f"{API}/tasks/{task}").json()["rule"]["exclusions"] == []


def test_unplanned_and_manual_attach(client: TestClient) -> None:
    connector = client.post(f"{API}/connectors", json={"type": "git", "config": {}}).json()["id"]
    task = client.post(
        f"{API}/tasks", json={"title": "Dotfiles", "plan": {"week_start": MONDAY}}
    ).json()
    occurrence = task["current_occurrence"]["id"]
    Git.script = [commits(("c9", "tweak zshrc"))]
    client.post(f"{API}/sync", json={"connector_id": connector})

    unplanned = client.get(f"{API}/events/unplanned", params={"week": MONDAY}).json()
    assert [e["title"] for e in unplanned["items"]] == ["tweak zshrc"]

    attached = client.post(
        f"{API}/occurrences/{occurrence}/evidence",
        json={"event_ids": [unplanned["items"][0]["id"]]},
    )
    assert attached.json()["status"] == "done"
    assert client.get(f"{API}/events/unplanned", params={"week": MONDAY}).json()["items"] == []


def test_rule_validation_and_removal(client: TestClient) -> None:
    connector, task = setup(client)
    bad = client.put(
        f"{API}/tasks/{task}/rule",
        json={
            "connector_id": connector,
            "kind": "commit",
            "filters": [{"field": "author", "op": "equals", "value": "x"}],
        },
    )
    assert bad.status_code == 422
    assert bad.json()["details"][0]["field"] == "filters.0"
    assert client.delete(f"{API}/tasks/{task}/rule").status_code == 204
    assert client.get(f"{API}/tasks/{task}").json()["rule"] is None
    assert client.delete(f"{API}/tasks/{task}/rule").status_code == 404
