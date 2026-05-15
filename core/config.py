import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dynamic Form Engine"
    API_V1_STR: str = "/api"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY")

    # Bot settings
    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")

    class Config:
        case_sensitive = True

settings = Settings()
