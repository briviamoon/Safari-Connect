from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.config.database import Base
from datetime import datetime, timezone


class OTP(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String)
    otp_code = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_used = Column(Boolean, default=False)