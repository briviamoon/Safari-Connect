from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.config.database import Base
from datetime import datetime, timezone
from app.utils.timezone import eat_timezone


class OTP(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String)
    otp_code = Column(String)
    created_at = Column(DateTime, default=eat_timezone())
    is_used = Column(Boolean, default=False)