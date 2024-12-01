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
from app.config.settings import settings
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import pytz, africastalking, subprocess, logging, platform, uuid, socket

router = APIRouter()
eat_timezone = pytz.timezone("Africa/Nairobi")

# init Africa's Talking SDK
username = settings.AFRICAS_TALKING_USERNAME
api_key = settings.AFRICAS_TALKING_API_KEY
africastalking.initialize(username, api_key)
sms = africastalking.SMS


########################################
# User Registration
@router.post("/register")
async def register_user(request: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user and send OTP for verification.
    """
    logging.info("Registering User")
    existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()

    if existing_user:
        logging.info(f"existing user found in database: {existing_user.phone_number}")
        logging.info("generating new otp ...")
        otp_code = generate_otp()
        logging.info(f"{existing_user.phone_number} OTP: {otp_code}")
        logging.info("Storing otp to database ...")
        store_otp(db, existing_user.phone_number, otp_code)
        logging.info("OTP Stored ...")
        logging.info(f"Sending SMS OTP to user {existing_user.phone_number}")
        #send_otp_sms(existing_user, otp_code)
        logging.info(f"OTP sent to {existing_user.phone_number}")
        return {"message": "User already registered. New OTP sent for verification."}

    try:
        logging.info(f"User not in database ... Adding user: {request.phone_number}")
        user = User(phone_number=request.phone_number, mac_address=request.mac_address)
        db.add(user)
        logging.info("commit to database ...")
        db.commit()
        
        logging.info("Generating OTP ...")
        otp_code = generate_otp()
        logging.info(f"New User {request.phone_number} OTP: {otp_code}")
        logging.info("Storing OTP ...")
        store_otp(db, request.phone_number, otp_code)
        logging.info("OTP Stored ...")
        logging.info("Sending OTP Via SMS ...")
        #send_otp_sms(request.phone_number, otp_code)
        logging.info("SMS Sent ...")
        return {"message": "Registration initiated. OTP sent for verification."}
    
    except Exception as e:
        logging.error(f"Error during user registration: {e}")
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
    #send_otp_sms(phone_number, otp_code)
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
            "subscription_active": user.is_active,
            "user_id": user.id
        }
        logging.info(f"No active subscription found for user {user.id}.")

    # Generate and return token
    logging.info("generating user access token ...")
    token = create_access_token(session_data)
    logging.info(f"Token generated for user {user.id}.")
    return {"access_token": token, "message": session_data["message"]}

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
def store_otp(db, phone_number: str, otp_code: str):
    """
    store the generated otp to db forspecific number
    """
    try:
        otp = OTP(
            phone_number=phone_number, 
            otp_code=otp_code, 
            is_used=False, 
            created_at=current_utc_time(), 
        )
        db.add(otp)
        db.commit()
        logging.info("CONFIRMED: OTP STORED SUCCESS ...")
    except Exception as e:
        db.rollback()
        print(f"Error storing OTP: {e}")
        raise


#Send OTP SMS
def send_otp_sms(phone_number: str, otp_code: str):
    logging.info(f"Trying to send OTP: {otp_code} ...")
    message = f"""
    Thank you for choosing Safariconnect 
    Your one time OTP code is: {otp_code}
    """
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
    