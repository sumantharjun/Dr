from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(tz=IST).replace(tzinfo=None)
