from fastapi import Request, HTTPException

# whitelisted IP addresses
ALLOWED_CALLBACK_IPS = [
    "196.201.214.200", "196.201.214.206", "196.201.213.114",
    "196.201.214.207", "196.201.214.208", "196.201.213.44",
    "196.201.212.127", "196.201.212.138", "196.201.212.129",
    "196.201.212.136", "196.201.212.74", "196.201.212.69"
]

# allow ip to give callback to the API's
async def allow_ip_middleware(request: Request, call_next):
    if request.url.path == "/payment/mpesa/callback" and request.client.host not in ALLOWED_CALLBACK_IPS:
        raise HTTPException(status_code=403, detail="Access denied: IP not Allowed")
    return await call_next(request)

