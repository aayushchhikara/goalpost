from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Settings loaded from the environment and .env. Missing required keys fail at startup."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_prefix="", extra="ignore"
    )

    timezone: str = Field(alias="GOALPOST_TIMEZONE")
    encryption_key: str = Field(alias="GOALPOST_ENCRYPTION_KEY", min_length=1)
    database_url: str = Field(
        default=f"sqlite:///{REPO_ROOT / 'data' / 'goalpost.db'}", alias="GOALPOST_DATABASE_URL"
    )
    frontend_origin: str = Field(default="http://localhost:3000", alias="GOALPOST_FRONTEND_ORIGIN")
    connectors_dir: Path = Field(default=REPO_ROOT / "connectors", alias="GOALPOST_CONNECTORS_DIR")
    # Comma-separated host names the API answers to; anything else is refused (DNS rebinding).
    allowed_hosts_csv: str = Field(default="localhost,127.0.0.1", alias="GOALPOST_ALLOWED_HOSTS")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone {value!r}, e.g. Asia/Kolkata") from exc
        return value

    @property
    def allowed_hosts(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts_csv.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
