import requests
from app.config.settings import settings
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from app.config.database import get_db
from app.models.payment_record import PaymentRecord
from app.config.settings import settings
from sqlalchemy.orm import Session
from sqlalchemy import engine
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker
import logging, json, base64, time

async def initiate_stk_push(phone_number: str, amount: float, reference: str, db: Session = Depends(get_db)):
        """Initiate STK push to customer's phone"""
        #phone number formating for safaricom API
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]  # Remove leading '+'
        elif phone_number.startswith("0"):
            phone_number = f"254{phone_number[1:]}"  # Convert '0' to '254'
            
        access_token = await get_access_token()
        password, timestamp = generate_password()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        payload = {
            "BusinessShortCode": settings.mpesa_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": settings.mpesa_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.callback_url,
            "AccountReference": f"Safari Connect. Session_ID: {reference}",
            "TransactionDesc": f"Payment for internet Subscription"
        }
        
        logging.info(f"Payload sent to M-Pesa: {json.dumps(payload, indent=4)}")
        
        try:
            response = requests.post(settings.callback_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logging.error(f"M-Pesa API Error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=400, detail="Failed to initiate payment")
            
            # Log the successful response
            print(f"M-Pesa Response: {response.json()}")
            
            #store data
            response_data = response.json()
            checkout_id = response_data.get('CheckoutRequestID')
            
            if not checkout_id:
                logging.error("No CheckoutRequestID in M-Pesa response.")
                raise HTTPException(status_code=400, detail="Missing checkout ID in M-Pesa response.")
            
            subscription_id = int(reference)
            
            #STORE IT
            storeed = store_checkout_request(checkout_id, subscription_id, db)
            if storeed:
                print(f"PaymentRecord stored successfully for CheckoutID: {checkout_id}")
            else:
                logging.error(f"Failed To store Checkot Requestfor CheckoutReaquestID: {checkout_id}")
                raise HTTPException(status_code=400, detail="Failed to store Checkout ID in database")
            
            return response_data
        
        except Exception as e:
            logging.error(f"Error initializing M-Pesa payment: {e}")
            raise HTTPException(status_code=500, detail="M-Pesa payment initialization failed")


#########################################


def generate_password(self):
        """Generate the M-Pesa password using the provided passkey"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = f"{settings.mpesa_shortcode}{settings.mpesa_passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode('utf-8'), timestamp


#########################################


async def get_access_token():
        """Get the access token required to make M-Pesa API calls"""
        if access_token and datetime.now() < access_token_expiry:
            return access_token

        credentials = base64.b64encode(
            f"{settings.mpesa_consumer_key}:{settings.mpesa_consumer_secret}".encode()
        ).decode('utf-8')

        response = requests.get(
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        result = response.json()
        access_token = result['access_token']
        # Token expires in 1 hour
        access_token_expiry = datetime.now() + timedelta(seconds=3599)
        return access_token


############################################
def store_checkout_request(checkout_id: str, subscription_id: int, db: Session):
    """When initiating an M-Pesa transaction, you will receive a CheckoutRequestID that serves as a unique identifier.
    Store this ID and subscription_id in the database to verify payment status later."""
    
    SessionLocal = sessionmaker(autocommit=False, bind=engine)
    db = SessionLocal()
    
    print(f"Storing checkout request - CheckoutID: {checkout_id}, SubscriptionID: {subscription_id}")
    
    try:
        payment_record = PaymentRecord(
            checkout_id=checkout_id,
            subscription_id=subscription_id,
            status="Pending"  # Initial status
        )
        db.add(payment_record)
        db.commit()  # Ensure async commit
        db.refresh(payment_record)
        print("Payment stored successfully")
        
        return True
    except Exception as e:
        print(f"Failed to store checkout request: {e}")
        raise HTTPException(status_code=500, detail="Failed to store payment record.")
    finally:
        db.close()