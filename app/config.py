"""
App settings loaded from environment variables (or .env file).
Add a .env file at the project root with your GEMINI_API_KEY to get started.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/transactions_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    
    # Gemini LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # FastAPI
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # CSV Processing
    MAX_FILE_SIZE_MB: int = 10
    BATCH_SIZE_LLM: int = 15  # Number of transactions per LLM call
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance"""
    return Settings()
