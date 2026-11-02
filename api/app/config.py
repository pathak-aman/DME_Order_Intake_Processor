import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        # Database: Defaults to local SQLite in /tmp for resilient serverless startup
        DATABASE_URL: str = "sqlite:////tmp/dme_orders.db"

        # JWT Authentication: Default key ensures server starts even before setting env vars
        SECRET_KEY: str = "genhealth-dme-default-secret-key-32-chars-long!"
        ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

        # Gemini Vision API
        GEMINI_API_KEY: str = ""

    settings = Settings()

except ImportError:
    # Graceful fallback for minimal / local test environments without pydantic-settings
    class FallbackSettings:
        def __init__(self):
            # Try reading .env file manually if exists
            env_file = ".env"
            if os.path.exists(env_file):
                try:
                    with open(env_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                os.environ.setdefault(k.strip(), v.strip().strip('"\''))
                except Exception:
                    pass

            self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/dme_orders.db")
            self.SECRET_KEY = os.getenv("SECRET_KEY", "genhealth-dme-default-secret-key-32-chars-long!")
            self.ALGORITHM = os.getenv("ALGORITHM", "HS256")
            self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
            self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    settings = FallbackSettings()
