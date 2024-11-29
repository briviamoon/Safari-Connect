# app/utils/timezone.py
from datetime import datetime, timezone
import pytz

def current_utc_time():
    return datetime.now().replace(tzinfo=timezone.utc)

def utc_to_eat(utc_time):
    eat_time_zone = pytz.timezone('Africa/Nairobi')
    return utc_time.astimezone(eat_time_zone)