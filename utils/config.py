try:
    from pydantic import BaseSettings
except ImportError:
    from pydantic.v1 import BaseSettings

class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    # Whether to force Playwright for all pages (True) or fallback to BS4 when possible.
    use_playwright: bool = True

    # Optional OpenAI API key for AI fallback parser.
    openai_api_key: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
