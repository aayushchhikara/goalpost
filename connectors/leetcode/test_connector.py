"""LeetCode connector tests. They run against recorded fixtures, never the live service."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from goalpost.sdk import SDK_VERSION, AuthError, ConnectorError, RateLimited, TransientError
from goalpost.sdk.loader import load_connector
from goalpost.services.dates import local_date
from goalpost.services.sync import validate_events

HERE = Path(__file__).parent
# Loaded the way the core loads it. Typed as Any to reach LeetCode's own `client` parameter.
LeetCode: Any = load_connector(HERE)
CONFIG = LeetCode.manifest.config.model_validate({"username": "example_user"})


def fixture(name: str) -> dict[str, Any]:
    return json.loads((HERE / "fixtures" / name).read_text())


def leetcode(handler: Callable[[dict[str, Any]], httpx.Response]) -> Any:
    """The connector with an HTTP client that answers from `handler` instead of the network."""
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return handler(body)

    connector = LeetCode(client=httpx.Client(transport=httpx.MockTransport(respond)))
    connector.requests = requests
    return connector


def recorded(body: dict[str, Any]) -> httpx.Response:
    """Answer each query from its recorded fixture."""
    query = body["query"]
    if "recentAcSubmissionList" in query:
        return httpx.Response(200, json=fixture("recent_ac.json"))
    if "question(" in query:
        return httpx.Response(200, json=fixture(f"question_{body['variables']['slug']}.json"))
    if "matchedUser" in query:
        return httpx.Response(200, json=fixture("user_found.json"))
    raise AssertionError(f"unexpected query: {query}")


def test_manifest_loads_and_declares_submissions() -> None:
    manifest = LeetCode.manifest
    assert (manifest.id, manifest.sdk_version, manifest.auth) == ("leetcode", SDK_VERSION, "none")
    kind = manifest.event_kind("submission")
    assert kind is not None
    assert kind.rule_fields == ["status", "difficulty", "problem", "language"]


def test_fetch_normalizes_submissions() -> None:
    connector = leetcode(recorded)
    result = connector.fetch(CONFIG, {}, None)

    assert [e.source_id for e in result.events] == ["1800000003", "1800000002", "1800000001"]
    newest = result.events[0]
    assert newest.kind == "submission"
    assert newest.occurred_at == datetime(2026, 10, 26, 18, 20, tzinfo=UTC)
    assert newest.payload == {
        "problem": "Two Sum",
        "slug": "two-sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "status": "accepted",
        "difficulty": "Easy",
        "language": "python3",
    }
    assert result.events[1].payload["difficulty"] == "Medium"
    assert result.cursor == {"last_timestamp": 1793038800}
    # One difficulty lookup per problem, not per submission.
    slugs = [r["variables"]["slug"] for r in connector.requests if "question(" in r["query"]]
    assert sorted(slugs) == ["merge-intervals", "two-sum"]


def test_events_pass_core_validation_and_land_on_the_right_day() -> None:
    result = leetcode(recorded).fetch(CONFIG, {}, None)
    valid, rejected = validate_events(LeetCode.manifest, result.events)
    assert rejected == []
    # Submitted at 23:50 IST on Monday: credit goes to Monday even if the sync runs at 3 am.
    assert local_date(valid[0][0].occurred_at, "Asia/Kolkata") == date(2026, 10, 26)


def test_cursor_skips_older_submissions() -> None:
    connector = leetcode(recorded)
    result = connector.fetch(CONFIG, {}, {"last_timestamp": 1792902600})
    # >= keeps the submission at the cursor itself; the core dedupes it.
    assert [e.source_id for e in result.events] == ["1800000003", "1800000002"]
    assert result.cursor == {"last_timestamp": 1793038800}


def test_nothing_new_keeps_the_cursor() -> None:
    result = leetcode(recorded).fetch(CONFIG, {}, {"last_timestamp": 1793038801})
    assert result.events == []
    assert result.cursor == {"last_timestamp": 1793038801}


def test_a_failed_difficulty_lookup_still_returns_the_submission() -> None:
    def no_difficulty(body: dict[str, Any]) -> httpx.Response:
        if "question(" in body["query"]:
            return httpx.Response(200, json={"errors": [{"message": "oops"}], "data": None})
        return recorded(body)

    result = leetcode(no_difficulty).fetch(CONFIG, {}, None)
    assert len(result.events) == 3
    assert result.events[0].payload["difficulty"] is None


def test_unknown_user_is_an_auth_error() -> None:
    connector = leetcode(lambda body: httpx.Response(200, json=fixture("user_missing.json")))
    with pytest.raises(AuthError, match="doesn't exist"):
        connector.fetch(CONFIG, {}, None)


def test_connection_test() -> None:
    assert leetcode(recorded).test_connection(CONFIG, {}) == "Found LeetCode user example_user"
    missing = leetcode(lambda body: httpx.Response(200, json=fixture("user_missing.json")))
    with pytest.raises(ConnectorError, match="No LeetCode user named 'example_user'"):
        missing.test_connection(CONFIG, {})


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429, headers={"Retry-After": "30"}), RateLimited),
        (httpx.Response(503), TransientError),
        (httpx.Response(403), TransientError),
        (httpx.Response(200, text="<html>bot check</html>"), TransientError),
        (httpx.Response(400), ConnectorError),
    ],
)
def test_http_failures_map_to_typed_errors(response: httpx.Response, error: type) -> None:
    with pytest.raises(error) as raised:
        leetcode(lambda body: response).fetch(CONFIG, {}, None)
    if error is RateLimited:
        assert raised.value.retry_after == 30.0


def test_network_failures_are_transient() -> None:
    def timeout(body: dict[str, Any]) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(TransientError, match="timed out"):
        leetcode(timeout).fetch(CONFIG, {}, None)
