"""Atomic sliding window shared across workers and agent restarts."""
import hashlib
import uuid
from fastapi import HTTPException
from app.config import settings
from app import redis_client

SLIDING_WINDOW = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000000 + tonumber(t[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000000)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil((tonumber(first[2]) + 60000000 - now) / 1000000))
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], 61)
return 0
"""

def check_rate_limit(key: str) -> None:
    digest = hashlib.sha256(key.encode()).hexdigest()
    redis_key = f"{settings.redis_key_prefix}:rate:{digest}"
    retry_after = int(redis_client.r.eval(SLIDING_WINDOW, 1, redis_key,
                                         settings.rate_limit_per_minute, uuid.uuid4().hex))
    if retry_after:
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(retry_after)})
