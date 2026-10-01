from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QueueLess"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://queueless:queueless@db:5432/queueless"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    email_host: str | None = None
    email_port: int = 587
    email_username: str | None = None
    email_password: str | None = None
    email_from: str = "noreply@queueless.local"
    password_reset_expire_minutes: int = 30
    frontend_url: str = "http://localhost:5173"
    rate_limit_login: str = "5/minute"
    rate_limit_queue_join: str = "10/minute"
    rate_limit_general: str = "100/minute"
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def cors_list(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def sync_database_url(self) -> str:
        """
        Synchronous psycopg URL for Celery workers.
        Replaces +asyncpg driver with +psycopg (psycopg v3 sync).
        """
        url = self.database_url
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "+psycopg")
        elif url.startswith("postgresql://") or url.startswith("postgresql+"):
            pass
        # If no driver specified, add psycopg
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings():
    return Settings()
