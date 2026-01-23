# python
# config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or `.env`."""
    DAISI_SECRET_KEY: str = Field(..., env="DAISI_SECRET_KEY")
    SESSION_SECRET_KEY: str = Field(..., env="SESSION_SECRET_KEY")
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
