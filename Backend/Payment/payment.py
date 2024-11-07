from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from Backend.database.dataBase import get_db, PaymentRecord, Subscription, engine
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from traceback import format_exc
import requests, logging, asyncio
import base64, time
from datetime import datetime, timedelta
import json, pytz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,  # This is the middleware_class argument
    allow_origins=["*"],  # Add your frontend URL in production
    allow_credentials=True,
    allow_methods= ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)

class MPESACredentials:
    CONSUMER_KEY = "O7VPs1yZAADxdI4nszyxI4lAN8IXCX2Glf0gRcNm5SgG5b48"
    CONSUMER_SECRET = "CrKa9Fu9hB65bpNKSF03ZWqCR8QdrHhvGZFjVRSRVM2Jb7ynfx7ctTtJUY0KEhKG"
    PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    BUSINESS_SHORT_CODE = "174379"  # Usually your Paybill number
    CALLBACK_URL = "https://f570-41-209-3-162.ngrok-free.app/payment/mpesa/callback"


class MPESAPayment:
    def __init__(self):
        self.access_token = None
        self.access_token_expiry = None
        
    def generate_password(self):
        """Generate the M-Pesa password using the provided passkey"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = f"{MPESACredentials.BUSINESS_SHORT_CODE}{MPESACredentials.PASSKEY}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode('utf-8'), timestamp
        
    async def get_access_token(self):
        """Get the access token required to make M-Pesa API calls"""
        if self.access_token and datetime.now() < self.access_token_expiry:
            return self.access_token
            
        credentials = base64.b64encode(
            f"{MPESACredentials.CONSUMER_KEY}:{MPESACredentials.CONSUMER_SECRET}".encode()
        ).decode('utf-8')
        
        response = requests.get(
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
            
        result = response.json()
        self.access_token = result['access_token']
        # Token expires in 1 hour
        self.access_token_expiry = datetime.now() + timedelta(seconds=3599)
        return self.access_token
        
    async def initiate_stk_push(self, phone_number: str, amount: float, reference: str, db: Session = Depends(get_db)):
        """Initiate STK push to customer's phone"""
        #phone number formating for safaricom API
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]  # Remove leading '+'
        elif phone_number.startswith("0"):
            phone_number = f"254{phone_number[1:]}"  # Convert '0' to '254'
        
        access_token = await self.get_access_token()
        password, timestamp = self.generate_password()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        payload = {
            "BusinessShortCode": MPESACredentials.BUSINESS_SHORT_CODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": MPESACredentials.BUSINESS_SHORT_CODE,
            "PhoneNumber": phone_number,
            "CallBackURL": MPESACredentials.CALLBACK_URL,
            "AccountReference": f"Safari Connect. Session_ID: {reference}",
            "TransactionDesc": f"Payment for internet Subscription"
        }
        
        logging.info(f"Payload sent to M-Pesa: {json.dumps(payload, indent=4)}")
        
        try:
            response = requests.post("https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest", headers=headers, json=payload)

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


# FastAPI routes for M-Pesa integration
@app.post("/mpesa/initiate")
async def initiate_payment(
    phone_number: str,
    amount: float,
    subscription_id: int,
    db: Session = Depends(get_db)
):
    print("Hit Gotten on /mpesa/initiate")
    mpesa = MPESAPayment()
    try:
        result = mpesa.initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            reference=str(subscription_id)
        )
        if result:
            print("\n We've gotten the STK Push\n\n")
    
        checkout_id = result.get('CheckoutRequestID')
        if not checkout_id:
            logging.error("No CheckoutRequestID received from M-Pesa.")
            raise HTTPException(status_code=400, detail="Failed to receive checkout ID from M-Pesa.")
        
        # Attempt to store the PaymentRecord
        storeed = await store_checkout_request(checkout_id, subscription_id, db)
        if storeed:
            print(f"PaymentRecord stored successfully for CheckoutID: {checkout_id}")
        else:
            logging.error(f"Failed To store Checkot Requestfor CheckoutReaquestID: {checkout_id}")
            raise HTTPException(status_code=400, detail="Failed to store Checkout ID in database")
        
        
    except Exception as e:
        logging.error(f"Failed to store PaymentRecord: {e}\n{format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to store payment record.")
    
    return {"message": "Payment initiated", "checkout_id": checkout_id}



@app.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    print("M-Pesa callback route hit\n")
    print(f"Received M-Pesa callback request\n.{request}")
    try:
        # Parse JSON payload
        stk_callback_response = await request.json()
        print(f"Parsed JSON payload: {stk_callback_response}")
        result = stk_callback_response.get('Body', {}).get('stkCallback', {})
        # Extract relevant fields from callback
        checkout_id = result.get('CheckoutRequestID')
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        
        print(f"Extracted Callback Details - CheckoutID: {checkout_id}, ResultCode: {result_code}, ResultDesc: {result_desc}")
        # Check if the ResultCode indicates success
        if result_code == 0:
            logging.info("Payment is successful. Extracting metadata...")
            
            # Extract metadata items and ensure all fields are available
            metadata = {item['Name']: item.get('Value') for item in result.get('CallbackMetadata', {}).get('Item', [])}
            amount = metadata.get("Amount")
            receipt_number = metadata.get("MpesaReceiptNumber")
            transaction_date_str = metadata.get("TransactionDate")
            phone_number = metadata.get("PhoneNumber")
            # Log extracted metadata
            print(f"Extracted Metadata - Amount: {amount}, ReceiptNumber: {receipt_number}, TransactionDate: {transaction_date_str}, PhoneNumber: {phone_number}")
            # Validate extracted metadata fields
            if not (amount and receipt_number and transaction_date_str and phone_number):
                logging.error("Incomplete metadata in M-Pesa callback.")
                raise HTTPException(status_code=400, detail="Incomplete callback metadata")
            # Ensure `transaction_date_str` is a string, as `strptime` expects a string
            if isinstance(transaction_date_str, int):
                transaction_date_str = str(transaction_date_str)
                
            # Convert transaction date to datetime object
            try:
                transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d%H%M%S")
            except ValueError as e:
                logging.error(f"Date parsing error: {e}")
                raise HTTPException(status_code=400, detail="Invalid date format in callback")
            
            # Fetch and proceed update PaymentRecord in the database if the CheckoutID was in there ro begin with
            print("Querying PaymentRecord from database.\n")
            retries = 10
            for attempt in range(retries):
                payment_record = db.query(PaymentRecord).filter(PaymentRecord.checkout_id == checkout_id).first()
                if payment_record:
                    break
                await asyncio.sleep(1)
            else:
                logging.warning(f"No PaymentRecord found for CheckoutID: {checkout_id}")
                raise HTTPException(status_code=404, detail="Payment record not found")
            
            print("PaymentRecord found. Updating with transaction details.")
            payment_record.amount = amount
            payment_record.mpesa_receipt_number = receipt_number
            payment_record.transaction_date = transaction_date
            payment_record.phone_number = phone_number
            payment_record.status = "Successful"
            db.commit()
            print("PaymentRecord updated and committed to database.")
            
            # Activate subscription
            print("Activating subscription for successful payment.")
            activated = await retry_callback_activation(checkout_id, db)
            if activated:
                print("Subscription activated successfully.")
                return {"message": "Payment processed successfully"}
        else:
            # Handle failed payment and mark as failed
            logging.info(f"Payment failed with ResultCode: {result_code}. Marking payment as failed.")
            await mark_payment_failed(checkout_id, db)
            logging.info("Payment marked as failed in database.")
            return {"message": f"Payment failed: {result_desc}"}
    except KeyError as e:
        logging.error(f"Missing field in callback data: {e}")
        raise HTTPException(status_code=400, detail="Invalid callback data format")
    except SQLAlchemyError as e:
        logging.error(f"Database error in processing callback: {e}")
        raise HTTPException(status_code=500, detail="Database error during callback processing")
    except Exception as e:
        logging.error(f"Unexpected error in callback processing: {e}")
        raise HTTPException(status_code=500, detail="Error processing callback data")


# handle retries if callback fails.
async def retry_callback_activation(checkout_id: str, db: Session, retries=100, delay=2):
    for attempt in range(retries):
        try:
            result = activate_subscription(checkout_id, db)
            if result:
                print("Subscription activated after callback.")
                return True
        except Exception as e:
            logging.error(f"Retry {attempt+1} failed: {e}")
            time.sleep(delay)
    logging.error(f"Failed to activate subscription after {retries} retries.")


def activate_subscription(checkout_id: str, db: Session):
    """Activate subscription after successful payment"""
    # Retrieve payment record
    payment_record = db.query(PaymentRecord).filter(PaymentRecord.checkout_id == checkout_id).first()
    
    if payment_record:
        # update the subscription status.
        subscription = db.query(Subscription).filter(Subscription.id == payment_record.subscription_id).first()
        if subscription:
            subscription.is_active = True
            db.commit()
            print("Subscription activated")
            return True
        else:
            logging.warning("Subscription Record Pending.. No Found in Database\n")
            raise HTTPException(status_code=400, detail="Subscription status not found on DataBasa\n")


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


async def mark_payment_failed(checkout_id: str, db: Session):
    """This function will mark the subscription as inactive or pending in case of payment failure."""
    # Retrieve the payment record
    payment_record = db.query(PaymentRecord).filter(PaymentRecord.checkout_id == checkout_id).first()
    
    if payment_record:
        # Update the subscription status as failed
        subscription = db.query(Subscription).filter(Subscription.id == payment_record.subscription_id).first()
        if subscription:
            subscription.is_active = False
            db.commit()
            print("Payment failed, subscription inactive")

