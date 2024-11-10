from pydantic import BaseModel

class SubscriptionCreate(BaseModel):
    user_id: int
    plan_type: str

