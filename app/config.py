"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wallet"
    # Use SQLite for local dev without Docker: "sqlite+aiosqlite:///./wallet.db"

    # App
    app_name: str = "Internal Wallet Service"
    debug: bool = False


settings = Settings()
