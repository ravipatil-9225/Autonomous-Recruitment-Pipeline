"""
Rate Limiter Setup (slowapi)
────────────────────────────
Provides a shared Limiter instance and the rate-limit exceeded handler.
Mount on the FastAPI app in main.py.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.app.config import settings

# Storage URI fallback for testing / local dev
storage_uri = settings.redis_url if not settings.debug else "memory://"

# Global limiter — keyed by client IP
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri=storage_uri,
)

rate_limit_handler = _rate_limit_exceeded_handler

__all__ = ["limiter", "RateLimitExceeded", "rate_limit_handler"]
