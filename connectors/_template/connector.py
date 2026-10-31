"""Template connector. Copy this folder to connectors/<id>/ and fill it in.

Folders starting with "_" are never loaded, so this file is safe to keep as is.
See connectors/leetcode/ for a complete, working example.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from goalpost.sdk import (
    SDK_VERSION,
    AuthKind,
    Connector,
    Event,
    EventKind,
    FetchResult,
    Manifest,
    SyncHints,
)
from pydantic import BaseModel, Field


class ExampleConfig(BaseModel):
    """Non-secret settings. The UI renders these as the setup form."""

    username: str = Field(min_length=1, description="Your username on the service")


class ExampleItem(BaseModel):
    """The payload of one event. Rules can filter on the fields listed in rule_fields."""

    title: str
    status: str


class ExampleConnector(Connector[ExampleConfig]):
    manifest = Manifest(
        id="example",  # must match the folder name
        name="Example",
        version="0.1.0",
        sdk_version=SDK_VERSION,
        description="What it tracks, in one sentence.",
        auth=AuthKind.NONE,  # or TOKEN, and list the .env keys in `secrets`
        config=ExampleConfig,
        secrets=[],
        event_kinds=[
            EventKind(name="item", payload=ExampleItem, rule_fields=["title", "status"]),
        ],
        sync_hints=SyncHints(min_interval=timedelta(hours=1), max_items=500),
    )

    def test_connection(self, config: ExampleConfig, secrets: Mapping[str, str]) -> str:
        # Make one cheap request. Raise ConnectorError (or AuthError) with a readable message.
        return f"Connected as {config.username}"

    def fetch(
        self, config: ExampleConfig, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> FetchResult:
        # Fetch only what happened since `cursor`, paginating up to max_items. Use the source's
        # own timestamps. Raise AuthError, RateLimited, TransientError or PartialResult on failure.
        # Never keep state anywhere but the returned cursor.
        items = [{"id": "1", "title": "Hello", "status": "done", "at": "2026-10-26T18:20:00Z"}]
        events = [
            Event(
                source_id=item["id"],
                kind="item",
                occurred_at=datetime.fromisoformat(item["at"]).astimezone(UTC),
                payload=ExampleItem(title=item["title"], status=item["status"]).model_dump(),
            )
            for item in items
        ]
        return FetchResult(events=events, cursor={"after": "1"})
