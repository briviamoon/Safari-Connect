from sqlalchemy import Column, Integer, String, DateTime, Float
from app.config.database import Base
from datetime import datetime, timezone


# base mode for Payment record in db
class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(Integer, primary_key=True, index=True)
    checkout_id = Column(String, unique=True, index=True)  # The M-Pesa transaction ID
    subscription_id = Column(Integer)  # Links to the Subscription table
    status = Column(String, default="Pending")  # Payment status
    amount = Column(Float, nullable=True)
    mpesa_receipt_number = Column(String, nullable=True)
    transaction_date = Column(DateTime, nullable=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

