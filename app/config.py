"""Application configuration."""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_DEFAULT = "sqlite+aiosqlite:///./wallet.db"


def _normalize_database_url(url: str) -> str:
    """Render gives postgres:// or postgresql://; asyncpg needs postgresql+asyncpg://."""
    if not url or url == SQLITE_DEFAULT:
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database: set DATABASE_URL for Postgres; omit for SQLite (single-service deploy)
    database_url: str = SQLITE_DEFAULT

    # App
    app_name: str = "Internal Wallet Service"
    debug: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: str | None) -> str:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return SQLITE_DEFAULT
        return _normalize_database_url(v) if isinstance(v, str) else v


settings = Settings()
