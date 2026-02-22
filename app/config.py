"""Application configuration."""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Render gives postgres:// or postgresql://; asyncpg needs postgresql+asyncpg://."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (DATABASE_URL on Render; postgres:// is auto-converted to postgresql+asyncpg://)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wallet"

    # App
    app_name: str = "Internal Wallet Service"
    debug: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        return _normalize_database_url(v) if isinstance(v, str) else v


settings = Settings()
