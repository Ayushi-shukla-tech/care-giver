from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://caregiver:caregiver@localhost:5432/caregiver"
    call_provider: str = "logging"
    otp_provider: str = "logging"
    weather_provider: str = "logging"
    suggestion_provider: str = "logging"
    groq_api_key: str = ""
    storage_provider: str = "logging"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_base_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket_name: str = ""
    prescription_extraction_provider: str = "logging"
    google_client_id: str = ""
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    patient_access_token_expire_minutes: int = 60 * 24 * 365

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
