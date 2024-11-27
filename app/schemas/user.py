from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    phone_number: str
    mac_address: str

class UserLogin(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+254\d{9}$")
