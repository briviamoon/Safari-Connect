from pydantic import BaseSettings

# environment variables
class Settings(BaseSettings):
    mpesa_consumer_key = "O7VPs1yZAADxdI4nszyxI4lAN8IXCX2Glf0gRcNm5SgG5b48"
    mpesa_consumer_secret = "CrKa9Fu9hB65bpNKSF03ZWqCR8QdrHhvGZFjVRSRVM2Jb7ynfx7ctTtJUY0KEhKG"
    mpesa_passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    mpesa_shortcode = "174379"
    callback_url = "https://f570-41-209-3-162.ngrok-free.app/payment/mpesa/callback"

    class Config:
        env_file = ".env"

settings = Settings()

