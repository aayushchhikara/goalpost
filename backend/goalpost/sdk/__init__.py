"""The connector SDK: everything a connector imports.

A connector is one folder under `connectors/` with a `connector.py` that defines a `Connector`
subclass and its `Manifest`. Connectors only fetch and normalize. Scheduling, retries,
secrets, validation, dedup and rules all live in the core.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import timedelta
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SDK_VERSION = 1


class AuthKind(StrEnum):
    NONE = "none"
    TOKEN = "token"
    OAUTH2 = "oauth2"


class EventKind(BaseModel):
    """One kind of event a connector emits, with the schema its payload must match."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = ""
    payload: type[BaseModel]
    rule_fields: list[str] = Field(
        default_factory=list, description="Payload fields rules filter on"
    )

    @model_validator(mode="after")
    def _rule_fields_exist(self) -> "EventKind":
        unknown = set(self.rule_fields) - set(self.payload.model_fields)
        if unknown:
            raise ValueError(f"rule_fields not in the {self.name} payload: {sorted(unknown)}")
        return self


class SyncHints(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_interval: timedelta = timedelta(hours=1)
    max_items: int = 500


class Manifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    version: str
    sdk_version: int
    description: str = ""
    icon: str = ""
    auth: AuthKind = AuthKind.NONE
    config: type[BaseModel] = Field(description="Non-secret settings, rendered as a form")
    secrets: list[str] = Field(default_factory=list, description="Names of .env keys it needs")
    event_kinds: list[EventKind]
    sync_hints: SyncHints = SyncHints()
    capabilities: list[str] = Field(default_factory=lambda: ["read"])

    def event_kind(self, name: str) -> EventKind | None:
        return next((k for k in self.event_kinds if k.name == name), None)


class Event(BaseModel):
    """A normalized event as a connector returns it. The core validates and stores it."""

    source_id: str = Field(min_length=1, description="Unique within the connector")
    kind: str
    occurred_at: AwareDatetime = Field(description="When it happened, from the source service")
    payload: dict[str, Any]


class FetchResult(BaseModel):
    events: list[Event]
    cursor: dict[str, Any] | None = Field(description="Saved only if the sync succeeds")


# Typed errors: the core decides what to do with each.


class ConnectorError(Exception):
    """A failure with a message readable by the user."""


class AuthError(ConnectorError):
    """Credentials or account are invalid. The core pauses the connector until it's fixed."""


class RateLimited(ConnectorError):
    """The service asked us to slow down. The core waits `retry_after` seconds and retries."""

    def __init__(self, message: str, retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TransientError(ConnectorError):
    """A network or server hiccup. The core retries with backoff."""


class PartialResult(ConnectorError):
    """Some events were fetched before a failure. The core keeps them."""

    def __init__(self, message: str, result: FetchResult) -> None:
        super().__init__(message)
        self.result = result


class Connector[ConfigT: BaseModel](ABC):
    """Base class for connectors. Instances are created fresh for every call."""

    manifest: ClassVar[Manifest]

    @abstractmethod
    def test_connection(self, config: ConfigT, secrets: Mapping[str, str]) -> str:
        """Check config and secrets. Return a short success message; raise ConnectorError."""

    @abstractmethod
    def fetch(
        self, config: ConfigT, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> FetchResult:
        """Return events since `cursor` plus the next cursor. Paginate internally."""


__all__ = [
    "SDK_VERSION",
    "AuthError",
    "AuthKind",
    "Connector",
    "ConnectorError",
    "Event",
    "EventKind",
    "FetchResult",
    "Manifest",
    "PartialResult",
    "RateLimited",
    "SyncHints",
    "TransientError",
]
