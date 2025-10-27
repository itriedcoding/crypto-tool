from __future__ import annotations
import time
from typing import Callable, Dict
from fastapi import Header, HTTPException, Request

# Simple token bucket per IP
class RateLimiter:
    def __init__(self, capacity: int = 60, refill_per_sec: float = 1.0):
        self.capacity = capacity
        self.tokens: Dict[str, float] = {}
        self.updated_at: Dict[str, float] = {}
        self.refill_per_sec = refill_per_sec

    def allow(self, ip: str) -> bool:
        now = time.time()
        last = self.updated_at.get(ip, now)
        tokens = min(
            self.capacity,
            self.tokens.get(ip, float(self.capacity)) + (now - last) * self.refill_per_sec,
        )
        if tokens < 1.0:
            self.tokens[ip] = tokens
            self.updated_at[ip] = now
            return False
        self.tokens[ip] = tokens - 1.0
        self.updated_at[ip] = now
        return True


rate_limiter = RateLimiter(capacity=120, refill_per_sec=2.0)


def verify_api_key(get_api_key: Callable[[], str]):
    async def _dependency(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(client_ip):
            raise HTTPException(status_code=429, detail="Too Many Requests")
        expected = get_api_key()
        if not expected or not x_api_key or x_api_key != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return _dependency
