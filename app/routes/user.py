from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.config.database import get_db, Base
from app.models.otp import OTP
from app.models.subscription import Subscription
from app.auth.security import SECRET_KEY, create_access_token
from app.schemas.user import UserCreate, UserLogin
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import pytz, africastalking, jwt, subprocess, logging, platform, uuid, socket

router = APIRouter()
eat_timezone = pytz.timezone("Africa/Nairobi")

africastalking.initialize(
    username='sandbox',
    api_key='atsk_2c126971a075f8c3ed0dbab580d1e4cb7959577587717d23e5fca0b6387104f4e7079690'
)
sms = africastalking.SMS


########################################
# register user
@router.post("/register")
async def register_user(request: UserCreate, db: Session = Depends(get_db)):
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
        logging.info(f"OTP for {request.phone_number}: {otp_code}")
        store_otp(db, request.phone_number, otp_code)
        send_otp_sms(request.phone_number, otp_code)

        return {"message": "Registration initiated. OTP sent for verification."}
    except IntegrityError as e:
        db.rollback()
        logging.error(f"IntegrityError while adding user {request.phone_number}: {e}")
        raise HTTPException(status_code=400, detail="User already exists or registration failed.")
    except Exception as e:
        logging.error(f"Unexpected error during user registration: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
####################################################

# RETURNING USERS #

@router.post("/login")
async def login_user(phone_number: UserLogin, db: Session = Depends(get_db)):
    # Check if the user is registered
    user = db.query(User).filter(User.phone_number == phone_number.phone_number).first()
    if not user:
        logging.info(f"user: {phone_number.phone_number}")
        raise HTTPException(status_code=400, detail="User not registered")

    # Generate and store OTP
    otp_code = generate_otp()
    store_otp(db, phone_number, otp_code)
    print(f"Returning OTP:{otp_code}\n")
    send_otp_sms(phone_number, otp_code)
    return {"message": "OTP sent to your phone"}


#######################################
# verify user's otp
class OtpRight (BaseModel):
    phone_number: str
    otp_code: str
@router.post("/verify-otp")
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
            active_subscription.end_time = active_subscription.end_time.astimezone(eat_timezone)
        
        time_left = active_subscription.end_time - datetime.now(eat_timezone)
        
        session_data = {
            "sub": user.phone_number,
            "message": "Hey, you enjoing the Internet?",
            "subscription_active": True,
            "time_left": time_left.total_seconds(),
            "plan_type": active_subscription.plan_type,
            "user_id":user.id
        }
    # if there are no active subscriptions
    else:
        session_data = {
            "sub": user.phone_number,
            "message": "Hello, Welcome back!",
            "subscription_active": False,
            "user_id": user.id
        }
    token = create_access_token(session_data)
    return {"token": token, "message": "Well, Your Session Is still active..."}
#######################################


# Generate 6 figure OTP
def generate_otp():
    # Generate 6-digit OTP
    import random
    return str(random.randint(100000, 999999))


#Store OTP in Database
def store_otp(db: Session, phone_number: str, otp_code: str):
    otp = OTP(phone_number=phone_number, otp_code=otp_code, is_used=False, created_at=datetime.now(eat_timezone))
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
    