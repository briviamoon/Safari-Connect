from datetime import datetime, timedelta
from jwt import jwt
from app.config.settings import settings
import secrets

# shields
SECRET_KEY = secrets.token_hex(64)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

def create_access_token(data: dict):
    """Generates access token with set expiry time,
    encryption algorythm and secret key"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorith=ALGORITHM)

def verify_token(token: str):
    """sends back the decoded token data"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.JWTError:
        return None

