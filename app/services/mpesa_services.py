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
import logging, json, base64, httpx, time


access_token = None
access_token_expiry = datetime.min

async def initiate_stk_push(phone_number: str, amount: float, reference: str, db: Session = Depends(get_db)):
        """Initiate STK push to customer's phone"""
        #phone number formating for safaricom API
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]  # Remove leading '+'
        elif phone_number.startswith("0"):
            phone_number = f"254{phone_number[1:]}"  # Convert '0' to '254'
            
        access_token = await get_access_token()
        password, timestamp = generate_password()
        
        print(f"Access Token Retrieved: {access_token}")
        
        if not access_token:
            logging.error("Access token was not obtained.")
            raise HTTPException(status_code=500, detail="Failed to obtain access token")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        payload = {
            "BusinessShortCode": settings.M_PESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": settings.M_PESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.CALLBACK_URL,
            "AccountReference": f"Safari Connect. Session_ID: {reference}",
            "TransactionDesc": f"Payment for internet Subscription"
        }
        
        print(f"Payload sent to M-Pesa: {json.dumps(payload, indent=4)}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = requests.post(
            'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            headers=headers,
            json=payload
        )            
            if response.status_code != 200:
                logging.error(f"M-Pesa API Error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=400, detail="Failed to initiate payment")
            
            # Log the successful response
            print(f"Response after Payload: \n\t{response.json()}")
            #store data
            response_data = response.json()
            logging.info(f"M-Pesa Response: {response.json()}")
            checkout_id = response_data.get('CheckoutRequestID')
            
            if not checkout_id:
                logging.error("No CheckoutRequestID in M-Pesa response.")
                raise HTTPException(status_code=400, detail="Missing checkout ID in M-Pesa response.")
            
            subscription_id = int(reference)
            
            #STORE IT
            storeed = store_checkout_request(checkout_id, subscription_id, db=db)
            if storeed:
                logging.info(f"PaymentRecord stored successfully for CheckoutID: {checkout_id}")
            else:
                logging.error(f"Failed To store Checkot Requestfor CheckoutReaquestID: {checkout_id}")
                raise HTTPException(status_code=400, detail="Failed to store Checkout ID in database")
            
            return response_data
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during M-Pesa request: {e}")
            raise HTTPException(status_code=500, detail="Network error during M-Pesa payment initialization")
        except KeyError as e:
            logging.error(f"Key error in M-Pesa response: {e}")
            raise HTTPException(status_code=400, detail="Unexpected M-Pesa response format")
        except Exception as e:
            logging.error(f"General error during M-Pesa payment initialization: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during payment initialization")

#########################################


def generate_password():
        """Generate the M-Pesa password using the provided passkey"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = f"{settings.M_PESA_SHORTCODE}{settings.M_PESA_PASSKEY}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode('utf-8'), timestamp


#########################################


async def get_access_token():
    print(f"creating access toke using \n\t{settings.M_PESA_CONSUMER_SECRET, settings.M_PESA_CONSUMER_KEY}")
    """Get the access token required to make M-Pesa API calls"""
    global access_token, access_token_expiry  # Ensure these are global if used outside this function

    # Check if an access token is already available and still valid
    if access_token and datetime.now() < access_token_expiry:
        return access_token
    

    credentials = base64.b64encode(
        f"{settings.M_PESA_CONSUMER_KEY}:{settings.M_PESA_CONSUMER_SECRET}".encode()
    ).decode('utf-8')
    
    print(f"these are the credentials: {credentials}")

    try:
        response = requests.get(
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        result = response.json()
        print(f"response from safaricom: \n{result}")
        access_token = result['access_token']  # Ensure this line executes successfully
        # Set token expiry (1 hour)
        access_token_expiry = datetime.now() + timedelta(seconds=3599)
        return access_token
    
    except KeyError as e:
        logging.error(f"Key error in access token response: {e}")
        raise HTTPException(status_code=400, detail="Invalid response format from access token request")
    except Exception as e:
        logging.error(f"Error fetching access token: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch access token")


############################################
def store_checkout_request(checkout_id: str, subscription_id: int, db: Session):
    """
    Store the M-Pesa checkout request in the database.
    """
    
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