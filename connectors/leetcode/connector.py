"""LeetCode: recent accepted submissions from a public profile, as `submission` events.

Uses LeetCode's unofficial GraphQL endpoint, so it's best-effort. The endpoint only returns the
last ~20 accepted submissions, so sync at least daily to avoid gaps.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from goalpost.sdk import (
    SDK_VERSION,
    AuthError,
    AuthKind,
    Connector,
    ConnectorError,
    Event,
    EventKind,
    FetchResult,
    Manifest,
    RateLimited,
    SyncHints,
    TransientError,
)
from pydantic import BaseModel, Field

GRAPHQL_URL = "https://leetcode.com/graphql"
RECENT_LIMIT = 20  # the endpoint caps recent submissions around 20
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": "Mozilla/5.0 (compatible; goalpost; +https://github.com/aayushchhikara/goalpost)",
}

RECENT_QUERY = """
query recent($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) { id title titleSlug timestamp lang }
}
"""
DIFFICULTY_QUERY = """
query difficulty($slug: String!) { question(titleSlug: $slug) { difficulty } }
"""
USER_QUERY = """
query user($username: String!) { matchedUser(username: $username) { username } }
"""


class LeetCodeConfig(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="Your public LeetCode username")


class Submission(BaseModel):
    problem: str = Field(description="Problem title, e.g. Two Sum")
    slug: str
    url: str
    status: Literal["accepted"] = "accepted"
    difficulty: Literal["Easy", "Medium", "Hard"] | None = None
    language: str | None = None


class LeetCodeConnector(Connector[LeetCodeConfig]):
    manifest = Manifest(
        id="leetcode",
        name="LeetCode",
        version="0.1.0",
        sdk_version=SDK_VERSION,
        description="Accepted submissions from your public LeetCode profile. No login needed.",
        icon="code",
        auth=AuthKind.NONE,
        config=LeetCodeConfig,
        event_kinds=[
            EventKind(
                name="submission",
                description="An accepted submission",
                payload=Submission,
                rule_fields=["status", "difficulty", "problem", "language"],
            )
        ],
        sync_hints=SyncHints(min_interval=timedelta(hours=1), max_items=RECENT_LIMIT),
    )

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=20.0, headers=HEADERS)

    def test_connection(self, config: LeetCodeConfig, secrets: Mapping[str, str]) -> str:
        data = self._query(USER_QUERY, {"username": config.username}, allow_errors=True)
        if not data.get("matchedUser"):
            raise ConnectorError(f"No LeetCode user named {config.username!r}")
        return f"Found LeetCode user {config.username}"

    def fetch(
        self, config: LeetCodeConfig, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> FetchResult:
        data = self._query(RECENT_QUERY, {"username": config.username, "limit": RECENT_LIMIT})
        submissions = data.get("recentAcSubmissionList") or []
        since = int((cursor or {}).get("last_timestamp", 0))

        # >= keeps same-second submissions; the core drops anything already saved.
        new = [s for s in submissions if int(s["timestamp"]) >= since]
        difficulties = {slug: self._difficulty(slug) for slug in {s["titleSlug"] for s in new}}
        events = [
            Event(
                source_id=str(s["id"]),
                kind="submission",
                occurred_at=datetime.fromtimestamp(int(s["timestamp"]), UTC),
                payload=Submission(
                    problem=s["title"],
                    slug=s["titleSlug"],
                    url=f"https://leetcode.com/problems/{s['titleSlug']}/",
                    difficulty=difficulties[s["titleSlug"]],
                    language=s.get("lang"),
                ).model_dump(),
            )
            for s in new
        ]
        latest = max([since, *(int(s["timestamp"]) for s in submissions)])
        return FetchResult(events=events, cursor={"last_timestamp": latest})

    def _difficulty(self, slug: str) -> Any:
        try:
            question = self._query(DIFFICULTY_QUERY, {"slug": slug}).get("question") or {}
        except ConnectorError:
            return None  # difficulty is a nice-to-have; don't fail the sync for it
        return question.get("difficulty")

    def _query(
        self, query: str, variables: dict[str, Any], *, allow_errors: bool = False
    ) -> dict[str, Any]:
        try:
            response = self._client.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        except httpx.TimeoutException as exc:
            raise TransientError("LeetCode timed out") from exc
        except httpx.TransportError as exc:
            raise TransientError(f"Couldn't reach LeetCode: {exc}") from exc

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimited(
                "LeetCode is rate limiting requests",
                retry_after=float(retry_after) if retry_after.isdigit() else 60.0,
            )
        if response.status_code >= 500 or response.status_code in (403, 408):
            # 403 is usually LeetCode's bot protection; it tends to pass on a later attempt.
            raise TransientError(f"LeetCode returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise ConnectorError(f"LeetCode returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise TransientError("LeetCode returned something other than JSON") from exc
        errors = body.get("errors") or []
        if errors and not allow_errors:
            message = errors[0].get("message", "unknown error")
            if "does not exist" in message:
                raise AuthError(f"LeetCode user {variables.get('username')!r} doesn't exist")
            raise ConnectorError(f"LeetCode error: {message}")
        return body.get("data") or {}
