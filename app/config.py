from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://fitagent:fitagent@localhost:5432/fitagent"
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""       # empty = official Claude API; set to an
                                       # Anthropic-compatible server (e.g. Ollama
                                       # http://localhost:11434) for free local models
    agent_model: str = "claude-sonnet-4-6"
    classifier_model: str = "claude-haiku-4-5-20251001"
    telegram_bot_token: str = ""       # one bot for all users; chat ids live in the users table
    swiggy_mcp_url: str = "https://mcp.swiggy.com/food"          # Food MCP, streamable HTTP
    swiggy_instamart_mcp_url: str = "https://mcp.swiggy.com/im"  # Instamart MCP, streamable HTTP
    swiggy_mock: bool = True           # per-user OAuth tokens live on the users row
    user_tz: str = "Asia/Kolkata"      # worker cron timezone (shared; per-user tz is a v2 upgrade)
    user_lat: float = 12.97            # legacy fallback — live Swiggy search is address-anchored
    user_lng: float = 77.59            # (users.lat/lng from PUT /me/location remain for display/future)

    class Config:
        env_file = ".env"
        extra = "ignore"  # .env legitimately holds vars we don't own (user notes,
                          # other tools) — newer pydantic-settings errors on them otherwise

settings = Settings()
