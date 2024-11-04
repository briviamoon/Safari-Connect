from fastapi.middleware.cors import CORSMiddleware
import random, socket, platform, uuid, logging
import requests, jwt, subprocess, sys, os, asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from Backend.Payment.payment import app as payment_app
from Backend.Payment.payment import MPESAPayment
from Backend.database.dataBase import get_db, Subscription, User, OTP
from typing import Optional
from pydantic import BaseModel
import africastalking

app = FastAPI()

app.mount("/payment", payment_app)
logging.info("Payment app mounted at /payment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify your allowed origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

S_KEY = "93f2d9b13fe90325b803bf2e8f9a66d205f3ff671990ac11423183d334d86691"


# Africa's Talking SMS configuration
africastalking.initialize(
    username='sandbox',
    api_key='atsk_2c126971a075f8c3ed0dbab580d1e4cb7959577587717d23e5fca0b6387104f4e7079690'
)
sms = africastalking.SMS

##########################################################################################

# Routes

@app.get("/")
async def root():
    return {
        "name": "Safari Connect Captive Portal API",
        "version": "1.0.0"
    }

############################################

#Get Client MAC ADDRESS

@app.get("/mac-address")
async def get_mac_address(req: Request):
    if not isinstance(req, Request):
        logging.error("Received a non-Request object.")
        return {
            "status": "error",
            "message": "Invalid request object"
        }

    try:
        print(f"Request type: {type(req)}")
        client_ip = req.client.host
        logging.info(f"Attempting to retrieve MAC for IP: {client_ip}")
        
        # if async is still waiting ...
        if asyncio.iscoroutinefunction(get_mac_from_ip):
            mac_address = await get_mac_from_ip(client_ip)
        else:
            mac_address = get_mac_from_ip(client_ip)
        
        # Check if MAC address was successfully retrieved; otherwise use fallback
        if not mac_address:
            mac_address = "00:00:00:00:00:00"  # Placeholder for unobtainable MAC
        
        return {
            "status": "success" if mac_address else "error",
            "mac_address": mac_address,
            "client_ip": client_ip
        }
    except Exception as e:
        logging.error(f"Error in MAC address endpoint: {e}")
        return {
            "status": "error",
            "message": "An unexpected error occurred",
            "client_ip": client_ip if 'client_ip' in locals() else "unknown"
        }

######################################

# model for the registration request
class RegisterRequest(BaseModel):
    phone_number: str
    mac_address: str

@app.post("/register")
async def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if the user already exists
    existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if existing_user:
        # Resend OTP for the existing user
        otp_code = generate_otp()
        print(f"TOP: {otp_code}")
        store_otp(db, request.phone_number, otp_code)
        send_otp_sms(request.phone_number, otp_code)
        return {"message": "User already registered. New OTP sent for verification."}
    
    # If user does not exist, proceed to create a new entry
    try:
        user = User(phone_number=request.phone_number, mac_address=request.mac_address)
        db.add(user)
        db.commit()
        
        # Generate and send OTP for the new registration
        otp_code = generate_otp()
        print(f"TOP: {otp_code}")
        store_otp(db, request.phone_number, otp_code)
        send_otp_sms(request.phone_number, otp_code)
        
        return {"message": "Registration initiated. OTP sent for verification."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User registration failed due to a database error.")



#######################################

class OtpRight (BaseModel):
    phone_number: str
    otp_code: str

# Endpointto verify OTP
@app.post("/verify-otp")
async def verify_otp(re: OtpRight, db: Session = Depends(get_db)):
    #check is OTP is valid and not used
    otp = db.query(OTP).filter(
        OTP.phone_number == re.phone_number,
        OTP.otp_code == re.otp_code,
        OTP.is_used == False
    ).first()
    
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    #Then Mark It as Used
    otp.is_used = True
    db.commit()
    
    # Check if the user is registered
    user = db.query(User).filter(User.phone_number == re.phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not registered")
    
    #check for an active subscripiton.
    active_subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.is_active == True,
        Subscription.end_time > datetime.now(timezone.utc)
    ).first()

    #if there's an active subscription, Generate a token leading to the countdown to the end of their session.
    if active_subscription:
        # Convert `end_time` to UTC if it is offset-naive
        if active_subscription.end_time.tzinfo is None:
            active_subscription.end_time = active_subscription.end_time.replace(tzinfo=timezone.utc)
        
        time_left = active_subscription.end_time - datetime.now(timezone.utc)
        
        session_data = {
            "sub": user.phone_number,
            "message": "Hey, you enjoing the Internet?",
            "subscription_active": True,
            "time_left": time_left.total_seconds(),
            "plan_type": active_subscription.plan_type,
            "user_id":user.id
        }
        token = create_access_token(session_data)
        return {"token": token, "message": "Well, Your Session Is still active..."}
    
    # if there are no active subscriptions
    else:
        access_data = {
            "sub": user.phone_number,
            "message": "Hello, Welcome back!",
            "subscription_active": False,
            "user_id": user.id
        }
        token = create_access_token(access_data)
        return {"token": token, "message": "No active subscription. Pleade select a plan"}



#########################################################
# Base for subscription request components
class SubRequest (BaseModel):
    user_id: int
    plan_type: str

# Endpoint for Subscription Creation
@app.post("/subscribe")
async def create_subscription(request: SubRequest, db: Session = Depends(get_db)
):
    # Plan configurations
    plans = {
        "1hr": {"amount": 1, "duration": timedelta(hours=1)},
        "2hrs": {"amount": 25, "duration": timedelta(hours=2)},
        "3hrs": {"amount": 35, "duration": timedelta(hours=3)},
        "8hrs": {"amount": 80, "duration": timedelta(hours=8)},
        "12hrs": {"amount": 100, "duration": timedelta(hours=12)},
        "24hrs": {"amount": 150, "duration": timedelta(days=1)},
        "3 days": {"amount": 300, "duration": timedelta(days=3)},
        "1 week": {"amount": 550, "duration": timedelta(weeks=1)},
        "2 weeks": {"amount": 1000, "duration": timedelta(weeks=2)},
        "monthly": {"amount": 1750, "duration": timedelta(days=30)}
    }
    
    if request.plan_type not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan type")
    
    plan = plans[request.plan_type]
    subscription = Subscription(
        user_id=request.user_id,
        plan_type=request.plan_type,
        amount=plan["amount"],
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + plan["duration"]
    )
    print(f"Your subscription is \n {subscription}")
    db.add(subscription)
    db.commit()
    
    # Initiate M-Pesa payment
    response = await initiate_mpesa_payment(subscription.id, plan["amount"], db)
    
    return {"message": "Subscription initiated, payment pending", "mpesa_response": response}

##################################################

#creating a subscription status checker
@app.get("/subscription-status")
async def subscription_status(user_id: int, db: Session = Depends(get_db)):
    print("checking subscription status\n")
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.is_active == True
    ).first()
    logging.info(f"subscription for {subscription.user_id} is {subscription.is_active}\n")

    # Calculate time left in seconds if there's an active subscription
    if subscription:
        # Ensure `end_time` is timezone-aware
        if subscription.end_time.tzinfo is None:
            subscription.end_time = subscription.end_time.replace(tzinfo=timezone.utc)
        
        time_left = (subscription.end_time - datetime.now(timezone.utc)).total_seconds()
        return {"subscription_active": True, "time_left": max(time_left, 0)}
    
    # Return inactive status if no subscription found
    return {"subscription_active": False, "time_left": 0}


####################################################

# RETURNING USERS #

@app.post("/login")
async def login_user(phone_number: str, db: Session = Depends(get_db)):
    # Check if the user is registered
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not registered")

    # Generate and store OTP
    otp_code = generate_otp()
    store_otp(db, phone_number, otp_code)
    send_otp_sms(phone_number, otp_code)
    return {"message": "OTP sent to your phone"}

#################################################################################################

#### FUNCTIONS ####

# Generate 6 figure OTP
def generate_otp():
    # Generate 6-digit OTP
    import random
    return str(random.randint(100000, 999999))


#Store OTP in Database
def store_otp(db: Session, phone_number: str, otp_code: str):
    otp = OTP(phone_number=phone_number, otp_code=otp_code, is_used=False, created_at=datetime.now(timezone.utc))
    db.add(otp)
    db.commit()


#Send OTP SMS
def send_otp_sms(phone_number: str, otp_code: str):
    message = f"Your OTP code is: {otp_code}"
    try:
        response = sms.send(message, [phone_number])
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send SMS")


#Create an Access Token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)  # Expiry as needed
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, S_KEY, algorithm="HS256")
    return encoded_jwt



#Initialize Mpesa Payment
def initiate_mpesa_payment(subscription_id: int, amount: float, db: Session):
    # Retrieve the user's phone number from the database
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    user = db.query(User).filter(User.id == subscription.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    phone_number = user.phone_number
    mpesa_payment = MPESAPayment()
    
    try:
        # STK PUSH INITIATE
        print("Initiating Mpesa STK Push Now")
        response = mpesa_payment.initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            reference=str(subscription_id) # unique to match with callback
        )
        logging.info(f"In the initiate_mpesa_payment call, this is the response: \n {response}")
        return response
    except Exception as e:
        print(f"Error initializing payment: {e}")
        raise HTTPException(status_code=500, detail="M-Pesa payment initiaizaion failed")


def get_mac_from_ip(ip_address):
    """
    Attempt to retrieve MAC address for a given IP address using multiple methods.
    
    Args:
        ip_address (str): IP address to find MAC for
    
    Returns:
        str: MAC address if found, None otherwise
    """
    try:
        # Method 1: Use system-specific ARP commands
        os_system = platform.system().lower()
        
        if os_system == 'windows':
            try:
                # Windows ARP command
                result = subprocess.run(['arp', '-a', ip_address], 
                                        capture_output=True, 
                                        text=True, 
                                        timeout=5)
                # Parse ARP output to extract MAC
                for line in result.stdout.split('\n'):
                    if ip_address in line:
                        # Extract MAC address (typically in format xx-xx-xx-xx-xx-xx)
                        mac = line.split()[-1].replace('-', ':')
                        if mac and len(mac.split(':')) == 6:
                            return mac
            except Exception as e:
                logging.error(f"Windows ARP lookup failed: {e}")
        
        elif os_system in ['linux', 'darwin']:  # Linux or macOS
            try:
                # Linux/macOS ARP command
                result = subprocess.run(['arp', '-n', ip_address], 
                                        capture_output=True, 
                                        text=True, 
                                        timeout=5)
                # Parse ARP output to extract MAC
                for line in result.stdout.split('\n'):
                    if ip_address in line:
                        # Extract MAC address (typically in format xx:xx:xx:xx:xx:xx)
                        parts = line.split()
                        mac = parts[2] if len(parts) > 2 else None
                        if mac and len(mac.split(':')) == 6:
                            return mac
            except Exception as e:
                logging.error(f"Linux/macOS ARP lookup failed: {e}")
        
        # Method 2: Fallback to UUID (if above methods fail)
        # This will return a pseudo-MAC based on the system's UUID
        if ip_address == '127.0.0.1' or ip_address == '::1':
            return str(uuid.getnode())
        
        # Additional fallback: Try socket method
        try:
            hostname = socket.gethostbyaddr(ip_address)[0]
            # Attempt to get MAC via hostname (not reliable for remote IPs)
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                            for elements in range(0,2*6,2)][::-1])
            return mac
        except Exception as e:
            logging.error(f"Hostname MAC lookup failed: {e}")
        
        return None
    
    except Exception as e:
        logging.error(f"Unexpected error in get_mac_from_ip: {e}")
        return None
