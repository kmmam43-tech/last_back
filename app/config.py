from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "배움결"
    app_env: str = "development"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://last-front-1cuh.netlify.app"
    openai_api_key: str = ""
    openai_model: str = ""
    openai_image_model: str = "gpt-image-2.6-flare"
    storage_backend: str = "memory"
    firebase_project_id: str = ""
    firestore_database_id: str = "(default)"
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    @property
    def agents_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)

    @property
    def image_generation_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_image_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()

