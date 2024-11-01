from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta, timezone
from Backend.Payment.FastAPI import MPESAPayment
import africastalking
import requests
import jwt
from typing import Optional

app = FastAPI()
Base = declarative_base()


# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    mac_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    is_used = Column(Boolean, default=False)


# Database connection
DATABASE_URL = "postgresql://user:password@localhost/captive_portal"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoload=True, bind=engine)


# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Africa's Talking SMS configuration
africastalking.initialize(
    username='YOUR_USERNAME',
    api_key='YOUR_API_KEY'
)
sms = africastalking.SMS


# Routes
@app.post("/register")
async def register_user(phone_number: str, mac_address: str, db: Session = Depends(get_db)):
    user = User(phone_number=phone_number, mac_address=mac_address)
    db.add(user)
    db.commit()
    
    # Generate and send OTP
    otp_code = generate_otp()
    store_otp(db, phone_number, otp_code)
    send_otp_sms(phone_number, otp_code)
    
    return {"message": "Registration initiated"}


# Endpointto verify OTP
@app.post("/verify-otp")
async def verify_otp(phone_number: str, otp_code: str, db: Session = Depends(get_db)):
    otp = db.query(OTP).filter(
        OTP.phone_number == phone_number,
        OTP.otp_code == otp_code,
        OTP.is_used == False
    ).first()
    
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    otp.is_used = True
    db.commit()
    
    # Generate JWT token
    token = create_access_token(phone_number)
    return {"token": token}


# Endpoint for Subscription Creation
@app.post("/subscribe")
async def create_subscription(
    user_id: int,
    plan_type: str,
    db: Session = Depends(get_db)
):
    # Plan configurations
    plans = {
        "1hr": {"amount": 10, "duration": timedelta(hours=1)},
        "2hrs": {"amount": 25, "duration": timedelta(hours=2)},
        "5hrs": {"amount": 65, "duration": timedelta(hours=5)},
        "monthly": {"amount": 500, "duration": timedelta(days=30)}
    }
    
    if plan_type not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan type")
    
    plan = plans[plan_type]
    subscription = Subscription(
        user_id=user_id,
        plan_type=plan_type,
        amount=plan["amount"],
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + plan["duration"]
    )
    
    db.add(subscription)
    db.commit()
    
    # Initiate M-Pesa payment
    response = initiate_mpesa_payment(subscription.id, plan["amount"], db)
    
    return {"message": "Subscription initiated, payment pending", "mpesa_response": response}


#### FUNCTIONS ####

# Helper functions
def generate_otp():
    # Generate 6-digit OTP
    import random
    return str(random.randint(100000, 999999))

def store_otp(db: Session, phone_number: str, otp_code: str):
    otp = OTP(phone_number=phone_number, otp_code=otp_code)
    db.add(otp)
    db.commit()

def send_otp_sms(phone_number: str, otp_code: str):
    message = f"Your OTP code is: {otp_code}"
    try:
        response = sms.send(message, [phone_number])
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send SMS")

def create_access_token(phone_number: str):
    to_encode = {"sub": phone_number}
    encoded_jwt = jwt.encode(to_encode, "YOUR_SECRET_KEY", algorithm="HS256")
    return encoded_jwt

def initiate_mpesa_payment(subscription_id: int, amount: float, db: Session):
    # Retrieve the user's phone number from the database
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    user = db.query(User).filter(User.id == subscription.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    phone_number = user.phone_number
    mpesa_payment = mpesa_payment()
    
    try:
        # STK PUSH INITIATE
        response = mpesa_payment.initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            reference=str(subscription_id) # unique to match with callback
        )
        return response
    except Exception as e:
        print(f"Error initializing payment: {e}")
        raise HTTPException(status_code=500, detail="M-Pesa payment initiaizaion failed")
    

# Create database tables
Base.metadata.create_all(bind=engine)