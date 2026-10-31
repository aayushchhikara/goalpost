import datetime as dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from goalpost.models.enums import SyncStatus, SyncTrigger
from goalpost.sdk import AuthKind

# Connector types (installed manifests)


class SecretRequirement(BaseModel):
    name: str = Field(description="The .env key")
    present: bool = Field(description="Whether the key is set in .env or the environment")


class EventKindRead(BaseModel):
    name: str
    description: str
    payload_schema: dict[str, Any]
    rule_fields: list[str]


class ConnectorTypeRead(BaseModel):
    id: str
    name: str
    version: str
    description: str
    icon: str
    auth: AuthKind
    config_schema: dict[str, Any] = Field(description="JSON Schema for the setup form")
    secrets: list[SecretRequirement]
    event_kinds: list[EventKindRead]
    min_sync_interval_minutes: int
    max_items: int
    capabilities: list[str]


class ConnectorLoadProblem(BaseModel):
    folder: str
    message: str


class ConnectorTypesResponse(BaseModel):
    items: list[ConnectorTypeRead]
    load_errors: list[ConnectorLoadProblem] = Field(
        description="Connector folders that failed to load"
    )


# Connector instances


class ConnectorCreate(BaseModel):
    type: str = Field(description="A connector type id, e.g. leetcode")
    name: str | None = Field(default=None, description="Defaults to the type's name")
    config: dict[str, Any] = Field(default_factory=dict)
    secret_ref: str | None = Field(
        default=None, description="The .env key holding the secret, if not the type's default"
    )


class SyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_id: str
    trigger: SyncTrigger
    started_at: dt.datetime
    finished_at: dt.datetime | None
    status: SyncStatus | None = Field(description="Null while the run is in progress")
    events_added: int
    error: str | None


class ConnectorStatus(StrEnum):
    NEVER_SYNCED = "never_synced"
    SYNCING = "syncing"
    OK = "ok"
    FAILING = "failing"
    PAUSED = "paused"
    DISABLED = "disabled"


class ConnectorRead(BaseModel):
    id: str
    type: str
    name: str
    config: dict[str, Any]
    secret_ref: str | None
    enabled: bool
    pause_reason: str | None = Field(description="Set when an auth error paused the connector")
    status: ConnectorStatus
    last_run: SyncRunRead | None
    last_success_at: dt.datetime | None


class ConnectorsResponse(BaseModel):
    items: list[ConnectorRead]


class ConnectorTestResult(BaseModel):
    ok: bool
    message: str


# Sync and status


class SyncRequest(BaseModel):
    connector_id: str | None = Field(default=None, description="Omit to sync every connector")


class SyncStarted(BaseModel):
    connector_ids: list[str] = Field(description="Connectors queued for this sync")


class SyncRunsResponse(BaseModel):
    items: list[SyncRunRead]
    next_before: str | None = Field(description="Pass as `before` to get older runs")


class ConnectorProblem(BaseModel):
    connector_id: str
    name: str
    message: str
    paused: bool


class StatusResponse(BaseModel):
    inbox_count: int = Field(description="Pending suggestions in the Proof Inbox")
    backlog_count: int
    syncing: bool
    last_sync_at: dt.datetime | None
    next_sync_at: dt.datetime | None
    connector_errors: list[ConnectorProblem]
