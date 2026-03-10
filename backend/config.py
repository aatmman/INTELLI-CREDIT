"""
INTELLI-CREDIT Configuration Module
Reads all environment variables using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: Optional[str] = None

    # --- Firebase Auth ---
    FIREBASE_SERVICE_ACCOUNT_JSON: str = "./firebase-service-account.json"

    # --- Groq (LLM) ---
    GROQ_API_KEY: str = ""

    # --- OpenAI (fallback) ---
    OPENAI_API_KEY: Optional[str] = None

    # --- Tavily (Web Research) ---
    TAVILY_API_KEY: str = ""

    # --- Databricks ---
    DATABRICKS_HOST: Optional[str] = None
    DATABRICKS_TOKEN: Optional[str] = None

    # --- ML Models ---
    ML_MODEL_PATH: str = "./ml/models/"

    # --- App Config ---
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
