from fastapi import FastAPI, Depends, security, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config.database import create_database
from app.middleware.ip_whitelist import allow_ip_middleware
from app.routes import user, subscription, payment, mac_address
from app.auth.security import SECRET_KEY
import jwt

app = FastAPI()

# Configure CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares
app.middleware("http")(allow_ip_middleware)

# Routes
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(subscription.router, prefix="/subscription", tags=["Subscription"])
app.include_router(payment.router, prefix="/Payment", tags=["Payment"])
app.include_router(mac_address.router, prefix="/mac-address", tags=["MAC Address"])

# Init Db
create_database()

# root of app
@app.get("/")
async def root():
    return {"message": "Welcome to Safari Connect Captive Portal API"}

# Check on the Sesion Token
# dependency function when I need a user session validated
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload # maybe I'll return a user ID for other checks later.
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

@app.get("/protected-endpoint")
async def protected_route(user:dict = Depends(get_current_user)):
    return {"message": "Access granted", "user": user}