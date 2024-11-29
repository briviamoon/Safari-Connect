from datetime import datetime, timedelta
import logging
from app.config.settings import settings
from app.utils.timezone import current_utc_time
from fastapi import HTTPException, status
from jose import JWTError, jwt

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # Token expiration time in minutes

def create_access_token(data: dict) -> str:
    """
    Create a JWT access token with an expiration time.
    """
    try:
        logging.info("encoding User Data ...")
        to_encode = data.copy()
        logging.info("setting Expiry time ...")
        expire = current_utc_time() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        logging.info(f"Expiry set to: {expire}")
        logging.info("Updating data with expiration time")
        to_encode.update({"exp": expire})
        logging.info("updated data with expiration time ...")
        logging.info("encoding User Data to Session Token ...")
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logging.info(f"Encoded token is now: {encoded_jwt}")
        return encoded_jwt
    except Exception as e:
        logging.error(f"Error creating token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating token: {str(e)}",
        )


def verify_token(token: str):
    """
    Verify a JWT token and return the decoded payload.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT decoding failed: {str(e)}",
        )
