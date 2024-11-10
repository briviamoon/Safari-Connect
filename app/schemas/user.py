from pydantic import BaseModel

class UserCreate(BaseModel):
    phone_number: str
    mac_address: str

