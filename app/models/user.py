from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.config.database import Base

# base model for A user in db
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    mac_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

