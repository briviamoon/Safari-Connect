from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models.user import User
from app.config.database import get_db, Base
from app.models.otp import OTP
from app.models.subscription import Subscription
from app.auth.security import SECRET_KEY, create_access_token
from app.schemas.user import UserCreate, UserLogin
from app.utils.timezone import utc_to_eat, current_utc_time
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
    print("Regisering User\n")
    existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if existing_user:
        # Resend OTP for the existing user
        print("Calling OTP Verification\n")
        otp_code = generate_otp()
        print(f"YOUR OTP: {otp_code}")
        store_otp(db, request.phone_number, otp_code)
        send_otp_sms(request.phone_number, otp_code)
        return {"message": "User already registered. New OTP sent for verification."}
    else:
        print("Database issues\n")

    # If user does not exist, proceed to create a new entry
    try:
        user = User(phone_number=request.phone_number, mac_address=request.mac_address)
        with db.begin():
            db.add(user)
            db.commit()

        # Generate and send OTP for the new registration
        otp_code = generate_otp()
        print(f"otp: {otp_code}")
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

########################################
# check us's subscpion
@router.get("/check-subscription")
async def check_subscription_status(user_id: int, db: Session = Depends(get_db)):
    """
    Endpoint to check if a user has an active subscription.
    """
    try:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True,
            Subscription.end_time > datetime.now(timezone.utc)
        ).first()

        if subscription:
            # just make sure of timezone awareness here.
            if subscription.end_time.tzinfo is None:
                subscription.end_time = subscription.end_time.replace(tzinfo=timezone.utc)
                
            time_left = (subscription.end_time - current_utc_time()).total_seconds()
            return {"subscription_active": True, "time_left": max(time_left, 0)}
        else:
            return {"subscription_active": False, "time_left": 0}

    except SQLAlchemyError as e:
        logging.error(f"Database error while checking subscription for user {user_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "Error checking subscription status"})
    except Exception as e:
        logging.error(f"Unexpected error for user {user_id}: {e}")
        return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})


#######################################
# verify user's otp
class OtpRight (BaseModel):
    phone_number: str
    otp_code: str
@router.post("/verify-otp")
async def verify_otp(re: OtpRight, db: Session = Depends(get_db)):
    
    print("verifying otp...")
    # Validate OTP
    otp = db.query(OTP).filter(
        OTP.phone_number == re.phone_number,
        OTP.otp_code == re.otp_code,
        OTP.is_used == False
    ).first()

    if not otp:
        logging.warning(f"Invalid OTP attempt for phone number: {re.phone_number}")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Mark OTP as used
    otp.is_used = True
    db.commit()
    logging.info(f"OTP {re.otp_code} for phone number {re.phone_number} marked as used.")

    # Fetch the user
    user = db.query(User).filter(User.phone_number == re.phone_number).first()
    if not user:
        logging.error(f"User not found for phone number: {re.phone_number}")
        raise HTTPException(status_code=404, detail="User not registered")
    logging.info(f"User {user.id} found for phone number {re.phone_number}")

    # Check for an active subscription
    active_subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.is_active == True,
        Subscription.end_time > datetime.now(timezone.utc)
    ).first()

    # Prepare session data
    if active_subscription:
        time_left = (active_subscription.end_time - datetime.now(timezone.utc)).total_seconds()
        session_data = {
            "sub": user.phone_number,
            "message": "Enjoying your Internet?",
            "subscription_active": True,
            "time_left": time_left,
            "plan_type": active_subscription.plan_type,
            "user_id": user.id
        }
        logging.info(f"Active subscription found for user {user.id}. Time left: {time_left}s")
    else:
        session_data = {
            "sub": user.phone_number,
            "message": "Welcome back!",
            "subscription_active": False,
            "user_id": user.id
        }
        logging.info(f"No active subscription found for user {user.id}.")

    # Generate and return token
    token = create_access_token(session_data)
    logging.info(f"Token generated for user {user.id}.")
    return {"token": token, "message": session_data["message"]}

#######################################

# serve the OTP verification templates back using a GET route
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/otp-verification", response_class=HTMLResponse)
async def otp_verification_page(request: Request):
    return templates.TemplateResponse("otp_verification.html", {"request": request})


@router.get("/log-in", response_class=HTMLResponse)
async def returnlogin(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
#######################################

# Generate 6 figure OTP
def generate_otp():
    # Generate 6-digit OTP
    import random
    otp = random.randint(100000, 999999)
    print("Generated The OTP\n")
    return otp


#Store OTP in Database
def store_otp(db: Session, phone_number: str, otp_code: str):
    otp = OTP(phone_number=phone_number, otp_code=otp_code, is_used=False, created_at=current_utc_time())
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
    