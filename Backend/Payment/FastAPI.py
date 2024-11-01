from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from Backend.database.dataBase import get_db, PaymentRecord, Subscription
from pydantic import BaseModel
from sqlalchemy.orm import Session
import requests
import base64
from datetime import datetime, timedelta
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as per your needs
    allow_credentials=True,
    allow_methods=["*"],  # This allows all HTTP methods
    allow_headers=["*"],  # This allows all headers
)

class MPESACredentials:
    CONSUMER_KEY = "O7VPs1yZAADxdI4nszyxI4lAN8IXCX2Glf0gRcNm5SgG5b48"
    CONSUMER_SECRET = "CrKa9Fu9hB65bpNKSF03ZWqCR8QdrHhvGZFjVRSRVM2Jb7ynfx7ctTtJUY0KEhKG"
    PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    BUSINESS_SHORT_CODE = "174379"  # Usually your Paybill number
    CALLBACK_URL = "https://1b61-41-209-3-162.ngrok-free.app"


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
        
    async def initiate_stk_push(self, phone_number: str, amount: float, reference: str):
        """Initiate STK push to customer's phone"""
        access_token = await self.get_access_token()
        password, timestamp = self.generate_password()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
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
            "AccountReference": reference,
            "TransactionDesc": f"WiFi Subscription {reference}"
        }
        
        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to initiate payment")
            
        return response.json()


# FastAPI routes for M-Pesa integration
@app.post("/mpesa/initiate")
async def initiate_payment(
    phone_number: str,
    amount: float,
    subscription_id: int,
    background_tasks: BackgroundTasks
):
    mpesa = MPESAPayment()
    result = await mpesa.initiate_stk_push(
        phone_number=phone_number,
        amount=amount,
        reference=str(subscription_id)
    )
    
    # Store the checkout request ID for verification
    background_tasks.add_task(
        store_checkout_request,
        checkout_id=result['CheckoutRequestID'],
        subscription_id=subscription_id
    )
    
    return {"message": "Payment initiated", "checkout_id": result['CheckoutRequestID']}



@app.post("/mpesa/callback")
async def mpesa_callback(payment_data: dict, db: Session = Depends(get_db)):
    """Handle M-Pesa callback"""
    try:
        # Extract payment details from callback
        result = payment_data['Body']['stkCallback']
        checkout_id = result['CheckoutRequestID']
        
        if result['ResultCode'] == 0:
            # Payment successful
            # Now to Update subscription status
            await activate_subscription(checkout_id, db)
            return {"message": "Payment processed successfully"}
        else:
            # Payment failed
            await mark_payment_failed(checkout_id, db)
            return {"message": "Payment failed"}
            
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid callback data")




async def store_checkout_request(checkout_id: str, subscription_id: int, db: Session):
    """When initiating an M-Pesa transaction, you will receive a CheckoutRequestID that serves as a unique identifier.
    Store this ID and subscription_id in the database to verify payment status later."""
    payment_record = PaymentRecord(
        checkout_id=checkout_id,
        subscription_id=subscription_id,
        status="Pending" # initial status
    )
    db.add(payment_record)
    db.commit()



async def activate_subscription(checkout_id: str, db: Session):
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