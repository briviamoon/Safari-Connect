from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config.database import init_database
from app.middleware.ip_whitelist import allow_ip_middleware
from app.routes import user, subscription, payment, mac_address
from app.config.settings import settings
from app.auth.deps import get_current_user
from dotenv import load_dotenv
import jwt, os

app = FastAPI()

# Configure templates and static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

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
app.include_router(payment.router, prefix="/payment", tags=["Payment"])
app.include_router(mac_address.router, prefix="/mac_address", tags=["MAC Address"])

# Init Db
init_database()

@app.on_event("startup")
def startup_event():
    load_dotenv() # Load environment variables on startup

# root of app
@app.get("/")
async def home(request: Request):
    ngrok_url = os.getenv("NGROK_URL")
    return templates.TemplateResponse("index.html", {"request": request, "ngrok_url": ngrok_url, "message":"HAllo Tes"})

# Check on the Session Token
# dependency function when I need a user session validated

@app.get("/protected-endpoint")
async def protected_route(user:dict = Depends(get_current_user)):
    return {"message": "Access granted", "user": user}

