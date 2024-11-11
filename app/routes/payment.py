from fastapi import APIRouter, Request, Depends, HTTPException
from app.models.payment_record import PaymentRecord
from app.models.subscription import Subscription
from app.config.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, time
import logging, traceback, asyncio

router = APIRouter()


##########################################


##########################################
@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    logging.info("M-Pesa callback route hit")
    logging.info(f"Received M-Pesa callback request\n.{request}")
    try:
        # Parse JSON payload
        stk_callback_response = await request.json()
        print(f"Parsed JSON payload: {stk_callback_response}")
        result = stk_callback_response.get('Body', {}).get('stkCallback', {})
        # Extract relevant fields from callback
        checkout_id = result.get('CheckoutRequestID')
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')

        logging.info(f"Extracted Callback Details - CheckoutID: {checkout_id}, ResultCode: {result_code}, ResultDesc: {result_desc}")
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
            logging.info(f"Extracted Metadata - Amount: {amount}, ReceiptNumber: {receipt_number}, TransactionDate: {transaction_date_str}, PhoneNumber: {phone_number}")
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
            logging.info("PaymentRecord updated and committed to database.")

            # Activate subscription
            logging.info("Activating subscription for successful payment.")
            activated = await retry_callback_activation(checkout_id, db)
            if activated:
                logging.info("Subscription activated successfully.")
                return {"message": "Payment processed successfully"}
            else:
                logging.error("Failed to activate subscription after payment.")
                raise HTTPException(status_code=500, detail="Failed to activate subscription")
        else:
            # Handle failed payment and mark as failed
            logging.info(f"Payment failed with ResultCode: {result_code}. Marking payment as failed.")
            await mark_payment_failed(checkout_id, db)
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


######################################
# handle retries if callback fails.
async def retry_callback_activation(checkout_id: str, db: Session, retries=10, delay=2):
    for attempt in range(1, retries+ 1):
        try:
            result = activate_subscription(checkout_id, db)
            if result:
                logging.info(f"Subscription activated on attempt {attempt}.")
                return True
        except Exception as e:
            logging.error(f"Retry {attempt+1} failed: {e}")
            await asyncio.sleep(delay * attempt)
            
    logging.error(f"Failed to activate subscription after {retries} retries.")
    return False


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