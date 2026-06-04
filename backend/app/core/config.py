from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Story"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://ai_story:ai_story@localhost:5432/ai_story"
    jwt_secret: str = "local-development-secret"
    access_token_minutes: int = 1440
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    milvus_uri: str = "http://localhost:19530"
    ollama_base_url: str = "http://localhost:11434"
    provider_api_key_encryption_secret: str = "local-provider-key-secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
