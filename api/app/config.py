from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database: Defaults to local SQLite in /tmp for resilient serverless startup
    # Override in production by setting DATABASE_URL in Vercel environment variables
    DATABASE_URL: str = "sqlite:////tmp/dme_orders.db"

    # JWT Authentication: Default key ensures the server starts even before setting env vars
    SECRET_KEY: str = "genhealth-dme-default-secret-key-32-chars-long!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Gemini Vision API (for Phase 3 PDF Extraction)
    GEMINI_API_KEY: str = ""


settings = Settings()
