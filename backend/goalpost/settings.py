from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
