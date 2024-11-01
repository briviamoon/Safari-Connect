import random, socket, platform, uuid, logging, requests, jwt, subprocess, sys, os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from Backend.Payment.FastAPI import MPESAPayment
from typing import Optional
from Backend.database.dataBase import get_db, Subscription, User, OTP
import africastalking

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as per your needs
    allow_credentials=True,
    allow_methods=["*"],  # This allows all HTTP methods
    allow_headers=["*"],  # This allows all headers
)

S_KEY = "93f2d9b13fe90325b803bf2e8f9a66d205f3ff671990ac11423183d334d86691"


# Africa's Talking SMS configuration
africastalking.initialize(
    username='sandbox',
    api_key='atsk_2c126971a075f8c3ed0dbab580d1e4cb7959577587717d23e5fca0b6387104f4e7079690'
)
sms = africastalking.SMS

##########################################################################################


#Get Client MAC ADDRESS
from fastapi import Request

@app.get("/mac-address")
async def get_mac_address(request: Request):
    # Try to retrieve the MAC address based on network setup; this might vary
    try:
        client_ip = request.client.host
        logging.info("ttempting to retreive MAC fro IP: {client_ip}")
        mac_address = get_mac_address(client_ip)
    
        if mac_address:
            return {
                "status": "success",
                "mac_address": mac_address,
                "client_ip": client_ip
            }
        else:
            return {
                "status": "error",
                "message": "MAC address could not be retreived",
                "client_ip": client_ip
            }
    except Exception as e:
        logging.error(f"Error in MAC address endpoint: {e}")
        return {
            "status": "error",
            "message": "An Unexpected error ocured",
            "client_ip": client_ip
        }
    

######################################


# Routes
@app.post("/register")
async def register_user(phone_number: str, mac_address: str, db: Session = Depends(get_db)):
    user = User(phone_number=phone_number, mac_address=mac_address)
    db.add(user)
    db.commit()
    
    # Generate and send OTP
    otp_code = generate_otp()
    print(f"OTP: {otp_code}")
    store_otp(db, phone_number, otp_code)
    send_otp_sms(phone_number, otp_code)
    
    return {"message": "Registration initiated"}


#######################################

# Endpointto verify OTP
@app.post("/verify-otp")
async def verify_otp(phone_number: str, otp_code: str, db: Session = Depends(get_db)):
    #check is OTP is valid and not used
    otp = db.query(OTP).filter(
        OTP.phone_number == phone_number,
        OTP.otp_code == otp_code,
        OTP.is_used == False
    ).first()
    
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    #Then Mark It as Used
    otp.is_used = True
    db.commit()
    
    # Check if the user is registered
    user = db.query(User).filter(User.phone_number == phone_number).first()
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
        time_left = active_subscription.endtime - datetime.now(timezone.utc)
        
        session_data = {
            "sub": user.phone_number,
            "message": "Hey, you enjoing the Internet?",
            "subscription_actve": True,
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

###############################

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
def create_access_token(phone_number: str):
    to_encode = {"sub": phone_number}
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
        response = mpesa_payment.initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            reference=str(subscription_id) # unique to match with callback
        )
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
