"""配置 — 从环境变量加载。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。所有字段必从环境变量读。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OBS
    OBS_AK: str = ""
    OBS_SK: str = ""
    OBS_ENDPOINT: str = ""
    OBS_BUCKET: str = "obs-mushroom"
    OBS_WORKDIR: str = "PixelHoard"

    # JWT
    JWT_SECRET: str = "dev-only-please-change"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:10388"

    # DB / Redis
    DATABASE_URL: str = "postgresql://pixelhoard:dev@postgres:5432/pixelhoard"
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_PASSWORD: str = ""


settings = Settings()