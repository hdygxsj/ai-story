from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Story"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://ai_story:ai_story@localhost:5432/ai_story"
    jwt_secret: str = "local-development-secret"
    access_token_minutes: int = 1440
    cors_origins: list[str] = ["http://localhost:5173"]
    milvus_uri: str = "http://localhost:19530"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
