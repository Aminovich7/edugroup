"""Rate limiting (slowapi) — brute-force hujumlaridan himoya.

Hisoblagich Redis'da saqlanadi, xotirada emas: ilova bir nechta uvicorn
worker yoki replika bilan ishlaganda har bir process o'z alohida hisoblagichiga
ega bo'lib qolardi va real limit bir necha barobar oshib ketardi.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
)

AUTH_RATE_LIMIT = settings.auth_rate_limit
