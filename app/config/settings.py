from pydantic_settings import BaseSettings

# environment variables
class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str
    M_PESA_CONSUMER_KEY: str  # Changed from MPESA_CONSUMER_KEY
    M_PESA_CONSUMER_SECRET: str  # Changed from MPESA_CONSUMER_SECRET
    M_PESA_PASSKEY: str  # Changed from MPESA_PASSKEY
    M_PESA_SHORTCODE: str  # Changed from MPESA_SHORTCODE
    CALLBACK_URL: str
    NGROK_URL: str

    class Config:
        env_file = ".env"

settings = Settings()

# print("Available environment variables:", os.environ.keys())
