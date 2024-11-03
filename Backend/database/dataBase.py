from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone

Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    mac_address = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    plan_type = Column(String)  # '1hr', '2hrs', '5hrs', 'monthly'
    amount = Column(Float)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=True)

class OTP(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String)
    otp_code = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_used = Column(Boolean, default=False)

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



# Database connection
DATABASE_URL = "postgresql://safariconnect:1Amodung%40%21.@192.168.0.102:5432/captive_portal"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, bind=engine)

#Ensuring the tables are created only once
inspector = inspect(engine)
if not inspector.get_table_names():  # Check if tables already exist
    print("Setting up database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

try:
    connection = engine.connect()
    print("DataBase Exists and Is connected successfully")
except Exception as e:
    print(f"Database connectio failed: {e}")

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()