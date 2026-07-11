from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://fitagent:fitagent@localhost:5432/fitagent"
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-4-6"
    classifier_model: str = "claude-haiku-4-5-20251001"
    telegram_bot_token: str = ""       # one bot for all users; chat ids live in the users table
    swiggy_mcp_url: str = ""
    swiggy_mcp_token: str = ""
    swiggy_mock: bool = True
    user_tz: str = "Asia/Kolkata"      # worker cron timezone (shared; per-user tz is a v2 upgrade)
    user_lat: float = 12.97            # Swiggy search fallback; per-user lat/lng live in users table
    user_lng: float = 77.59

    class Config:
        env_file = ".env"

settings = Settings()
