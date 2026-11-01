"""GitHub connector tests. They run against recorded fixtures, never the live service."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from goalpost.sdk import AuthError, ConnectorError, PartialResult, RateLimited, TransientError
from goalpost.sdk.loader import load_connector
from goalpost.services.dates import local_date
from goalpost.services.sync import validate_events
from pydantic import ValidationError

HERE = Path(__file__).parent
# Loaded the way the core loads it. Typed as Any to reach GitHub's own `client` parameter.
GitHub: Any = load_connector(HERE)
CONFIG = GitHub.manifest.config.model_validate({"repos": ["example-user/goalpost"]})
SECRETS = {"GITHUB_TOKEN": "ghp_test"}


def fixture(name: str) -> Any:
    return json.loads((HERE / "fixtures" / name).read_text())


def recorded(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/user":
        return httpx.Response(200, json=fixture("user.json"))
    if path.endswith("/commits"):
        return httpx.Response(200, json=fixture("commits.json"))
    if "/commits/" in path:
        return httpx.Response(200, json=fixture(f"commit_{path.rsplit('/', 1)[1]}.json"))
    if path.startswith("/repos/"):
        return httpx.Response(200, json=fixture("repo.json"))
    raise AssertionError(f"unexpected request: {path}")


def github(handler: Callable[[httpx.Request], httpx.Response]) -> tuple[Any, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(respond))
    return GitHub(client=client), requests


def test_manifest() -> None:
    manifest = GitHub.manifest
    assert (manifest.id, manifest.auth, manifest.secrets) == ("github", "token", ["GITHUB_TOKEN"])
    kind = manifest.event_kind("commit")
    assert kind is not None
    assert (kind.rule_fields, kind.title_field) == (
        ["repo", "branch", "path", "message"],
        "message",
    )


def test_fetch_normalizes_commits_and_skips_merges() -> None:
    connector, requests = github(recorded)
    result = connector.fetch(CONFIG, SECRETS, None)

    assert [e.source_id[:7] for e in result.events] == ["a3f9c21", "e91d0a6"]
    first, second = result.events
    assert first.payload == {
        "repo": "goalpost",
        "full_repo": "example-user/goalpost",
        "branch": "main",
        "path": ["frontend/components/screens/today.tsx", "frontend/app/today/page.tsx"],
        "message": "feat(frontend): today view layout",
        "sha": "a3f9c21000000000000000000000000000000001",
        "url": "https://github.com/example-user/goalpost/commit/a3f9c21000000000000000000000000000000001",
    }
    assert second.payload["message"] == "fix token refresh on expired session"  # first line only
    assert second.occurred_at == datetime(2026, 10, 26, 18, 20, tzinfo=UTC)
    assert local_date(second.occurred_at, "Asia/Kolkata") == date(2026, 10, 26)

    listing = next(r for r in requests if r.url.path.endswith("/commits"))
    assert listing.url.params["author"] == "example-user"
    assert listing.url.params["sha"] == "main"
    assert requests[0].headers["Authorization"] == "Bearer ghp_test"
    state = result.cursor["example-user/goalpost"]
    assert len(state["seen"]) == 2
    valid, rejected = validate_events(GitHub.manifest, result.events)
    assert (len(valid), rejected) == (2, [])


def test_later_syncs_look_back_a_week_and_skip_known_commits() -> None:
    connector, _ = github(recorded)
    first = connector.fetch(CONFIG, SECRETS, None)

    again, requests = github(recorded)
    result = again.fetch(CONFIG, SECRETS, first.cursor)
    assert result.events == []
    assert not [r for r in requests if "/commits/" in r.url.path]  # no detail refetches
    listing = next(r for r in requests if r.url.path.endswith("/commits"))
    last = datetime.fromisoformat(first.cursor["example-user/goalpost"]["last_sync"])
    assert datetime.fromisoformat(listing.url.params["since"]) == last - timedelta(days=7)


def test_an_empty_repository_has_no_commits() -> None:
    def empty(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits"):
            return httpx.Response(409, json={"message": "Git Repository is empty."})
        return recorded(request)

    connector, _ = github(empty)
    assert connector.fetch(CONFIG, SECRETS, None).events == []


def test_connection_test() -> None:
    connector, _ = github(recorded)
    assert connector.test_connection(CONFIG, SECRETS) == (
        "Signed in as example-user; can read example-user/goalpost"
    )


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        (httpx.Response(401), AuthError, "rejected the token"),
        (httpx.Response(403, headers={"X-RateLimit-Remaining": "0"}), RateLimited, "rate limit"),
        (httpx.Response(403), AuthError, "isn't allowed"),
        (httpx.Response(404), ConnectorError, "not found"),
        (httpx.Response(502), TransientError, "HTTP 502"),
    ],
)
def test_http_failures_map_to_typed_errors(
    response: httpx.Response, error: type, message: str
) -> None:
    def fail_on_repo(request: httpx.Request) -> httpx.Response:
        return recorded(request) if request.url.path == "/user" else response

    connector, _ = github(fail_on_repo)
    with pytest.raises(error, match=message):
        connector.fetch(CONFIG, SECRETS, None)


def test_a_failing_second_repo_keeps_the_first_repos_commits() -> None:
    config = GitHub.manifest.config.model_validate(
        {"repos": ["example-user/goalpost", "example-user/dotfiles"]}
    )

    def dotfiles_down(request: httpx.Request) -> httpx.Response:
        if "dotfiles" in request.url.path:
            return httpx.Response(503)
        return recorded(request)

    connector, _ = github(dotfiles_down)
    with pytest.raises(PartialResult) as raised:
        connector.fetch(config, SECRETS, None)
    partial = raised.value.result
    assert len(partial.events) == 2
    assert partial.cursor is not None
    assert "example-user/goalpost" in partial.cursor  # dotfiles is retried next sync
    assert "example-user/dotfiles" not in partial.cursor


@pytest.mark.parametrize("repos", [[], ["goalpost"], ["owner/name/extra"]])
def test_repos_must_be_owner_slash_name(repos: list[str]) -> None:
    with pytest.raises(ValidationError):
        GitHub.manifest.config.model_validate({"repos": repos})
