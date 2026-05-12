"""Simple thread-safe sliding-window rate limiter (no external dependencies)."""
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: int):
        self.max_calls = max_calls
        self.period = timedelta(seconds=period_seconds)
        self._log: dict[str, list[datetime]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = datetime.utcnow()
            cutoff = now - self.period
            recent = [t for t in self._log[key] if t > cutoff]
            if len(recent) >= self.max_calls:
                return False
            recent.append(now)
            self._log[key] = recent
            return True


# Shared limiter instances
login_limiter = RateLimiter(max_calls=5, period_seconds=60)       # 5 attempts / minute
register_limiter = RateLimiter(max_calls=3, period_seconds=300)   # 3 attempts / 5 minutes
