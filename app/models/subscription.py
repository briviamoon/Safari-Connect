from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.config.database import Base

# base model for Subscription in db

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    plan_type = Column(String)
    amount = Column(Float)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=False)

