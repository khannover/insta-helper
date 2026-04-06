from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    workers: int = 2
    cors_origins: str = "http://localhost:3000"
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MB
    upload_dir: str = "/app/uploads"


settings = Settings()
