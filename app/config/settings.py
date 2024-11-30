from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError


# noinspection PyArgumentList
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Provides default values and validation for critical settings.
    """
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    M_PESA_CONSUMER_KEY: str = Field(..., env="M_PESA_CONSUMER_KEY")
    M_PESA_CONSUMER_SECRET: str = Field(..., env="M_PESA_CONSUMER_SECRET")
    M_PESA_PASSKEY: str = Field(..., env="M_PESA_PASSKEY")
    M_PESA_SHORTCODE: str = Field(..., env="M_PESA_SHORTCODE")
    CALLBACK_URL: str = Field(..., env="CALLBACK_URL")
    NGROK_URL: str = Field(..., env="NGROK_URL")
    IPV4_CURRENT: str = Field(..., env="IPV4_CURRENT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

try:
    settings = Settings()
except ValidationError as e:
    print("Configuration Error: Ensure all required environment variables are set.")
    print(e.json())
    raise
