from pydantic import BaseModel

class PaymentCallback(BaseModel):
    checkout_id: str
    status: str
    amount: float

