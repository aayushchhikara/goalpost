from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, Enum, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column
from ulid import ULID

# Single user today; every row carries user_id so profiles can come later.
DEFAULT_USER_ID = "local"


def new_id() -> str:
    return str(ULID())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Aware UTC datetimes. SQLite drops tzinfo, so store naive UTC and restore it on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; pass a timezone-aware value")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def str_enum(enum: type[StrEnum]) -> Enum:
    """Store a StrEnum as its plain string value, without a native enum or CHECK constraint."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class IdMixin:
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)


class UserMixin:
    user_id: Mapped[str] = mapped_column(String(26), default=DEFAULT_USER_ID, index=True)
