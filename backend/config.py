"""Reads keys from backend/.env. The browser never receives the Supabase secret or the Gemini key."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    gemini_api_key: str
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
