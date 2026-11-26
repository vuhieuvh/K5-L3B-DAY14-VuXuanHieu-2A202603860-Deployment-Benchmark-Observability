"""Lazy connection: dependency failure must not stop liveness/startup."""
import redis
from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True,
                   socket_connect_timeout=1, socket_timeout=1,
                   retry_on_timeout=False, health_check_interval=30)

def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
