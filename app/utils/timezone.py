# app/utils/timezone.py
from datetime import datetime, timezone
import pytz

def eat_timezone():
    timezone_eat = pytz.timezone('Africa/Nairobi')
    return datetime.now(timezone_eat)