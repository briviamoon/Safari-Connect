from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth.deps import get_current_user
from app.config.database import init_database
from app.config.settings import settings
from app.middleware.ip_whitelist import allow_ip_middleware
from app.routes import user, subscription, payment, mac_address

app = FastAPI()

# Configure templates and static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

NGROK_URL = settings.NGROK_URL
ALLOWED_METHODS = ["*"]
ALLOWED_HEADERS = ["*"]
# Configure CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods= ALLOWED_METHODS,
    allow_headers= ALLOWED_HEADERS,
)

# Middlewares
app.middleware("https")(allow_ip_middleware)

# Routes
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(subscription.router, prefix="/subscription", tags=["Subscription"])
app.include_router(payment.router, prefix="/payment", tags=["Payment"])
app.include_router(mac_address.router, prefix="/mac_address", tags=["MAC Address"])

# Init Db
init_database()


@app.options("/mac_address/{mac_address}")
async def handle_options():
    return {"message": "CORS preflight request handled"}


# root of app
@app.get("/")
async def home(request: Request):
    ngrok_url = settings.NGROK_URL
    ipv4_url = settings.IPV4_CURRENT
    print(f"Serving This URL as API BASE: {ngrok_url}\n")
    return templates.TemplateResponse("index.html", {"request": request, "skibidi": ngrok_url, "rizz": ipv4_url})

# Check on the Session Token
# dependency function when I need a user session validated

@app.get("/protected-endpoint")
async def protected_route(user:dict = Depends(get_current_user)):
    return {"message": "Access granted", "user": user}

