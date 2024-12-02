from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.subscription import Subscription
from app.models.user import User
from app.config.database import get_db
from app.services.mpesa_services import initiate_stk_push
from app.utils.timezone import current_utc_time, utc_to_eat
from app.schemas.subscription import SubscriptionCreate
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta, timezone
import logging

router = APIRouter()

@router.post("/subscribe")
async def create_subscription(request: SubscriptionCreate, db: Session = Depends(get_db)):
    print(f"Received request: {request}")
    print(f"User ID from request: {request.user_id}")
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
    
    try:
        with db.begin():
            subscription = Subscription(
                user_id=request.user_id,
                plan_type=request.plan_type,
                amount=plan["amount"],
                start_time=current_utc_time(),
                end_time=current_utc_time() + plan["duration"],
                is_active=False
            )
        logging.info(f"Created subscription object: {subscription}")
        db.add(subscription)
        db.commit()
    
        # Initiate M-Pesa payment
        response = await initiate_mpesa_payment(subscription.id, plan["amount"], db=db)
        return {"message": "Subscription initiated, payment pending", "mpesa_response": response}
    
    except SQLAlchemyError as e:
        logging.error(f"Database error during subscription creation: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logging.error(f"Unexpected error during Subscription creation: {e}")
        raise HTTPException(status_code=500, detail="Unexpected server error")


#creating a subscription status checker
@router.get("/subscription-status")
async def subscription_status(user_id: int, db: Session = Depends(get_db)):
    print(f"Checking subscription status for user: {user_id}")
    
    # Query the subscription record for the given user_id
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        logging.info(f"No subscription found for user {user_id}")
        return {"subscription_active": False, "time_left": 0}

    logging.info(f"Subscription for user {subscription.user_id} is {'active' if subscription.is_active else 'inactive'}")
    
    # If the subscription is active, calculate the time left
    if subscription.is_active:
        if subscription.end_time:
            # Ensure `end_time` is timezone-aware
            if subscription.end_time.tzinfo is None:
                subscription.end_time = subscription.end_time.replace(tzinfo=timezone.utc)
            
            # Calculate time left in seconds
            time_left = (subscription.end_time - current_utc_time()).total_seconds()
            logging.info(f"Time left for user {user_id}: {time_left} seconds")
            return {"subscription_active": True, "time_left": max(time_left, 0)}

        # Handle case where `end_time` is None or invalid
        logging.warning(f"Subscription for user {user_id} has no valid end_time")
        return {"subscription_active": True, "time_left": 0}
    
    # If subscription is inactive
    return {"subscription_active": False, "time_left": 0}


def initiate_mpesa_payment(subscription_id: int, amount: float, db: Session):
    # Retrieve the user's phone number from the database
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    user = db.query(User).filter(User.id == subscription.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    phone_number = user.phone_number
    
    try:
        # STK PUSH INITIATE
        print("Initiating Mpesa STK Push Now")
        response = initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            reference=str(subscription_id), # unique to match with callback
            db=db
        )
        logging.info(f"In the initiate_mpesa_payment call, this is the response: \n {response}")
        return response
    except Exception as e:
        print(f"Error initializing payment: {e}")
        raise HTTPException(status_code=500, detail="M-Pesa payment initiaizaion failed")
    

# redirect user to plans
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/subscription-plans", response_class=HTMLResponse)
async def subscription_success_page(request: Request):
    return templates.TemplateResponse("subscription_plans.html", {"request": request})

@router.get("/buy-plans", response_class=HTMLResponse)
async def buy_subscription_plan(request: Request):
    return templates.TemplateResponse("plans.html", {"request": request})

@router.get("/buy-more-plans", response_class=HTMLResponse)
async def buy_more_plans(request: Request):
    return templates.TemplateResponse("more-plans.html", {"request": request})