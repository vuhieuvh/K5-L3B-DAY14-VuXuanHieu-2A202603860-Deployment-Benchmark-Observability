"""Atomic daily UTC budget in integer nano-USD, using lab mock prices.

Reserve before LLM, settle once afterwards. An interrupted process can leave
its reservation until expiry: fail closed rather than reset budget on restart.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import uuid
from fastapi import HTTPException
from app.config import settings
from app import redis_client

PRICE_INPUT_PER_1K = Decimal("0.00015")
PRICE_OUTPUT_PER_1K = Decimal("0.0006")
UNITS_PER_USD = 1_000_000_000

RESERVE = """
local spent = tonumber(redis.call('HGET', KEYS[1], 'spent') or '0')
local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0')
local amount = tonumber(ARGV[2])
local budget = tonumber(ARGV[1])
if spent + reserved >= budget or spent + reserved + amount > budget then
    return 0
end
redis.call('HINCRBY', KEYS[1], 'reserved', amount)
redis.call('HSET', KEYS[1], ARGV[3], amount)
redis.call('EXPIREAT', KEYS[1], ARGV[4])
return 1
"""

SETTLE = """
local held = redis.call('HGET', KEYS[1], ARGV[1])
if not held then return 0 end
redis.call('HINCRBY', KEYS[1], 'reserved', -tonumber(held))
redis.call('HINCRBY', KEYS[1], 'spent', ARGV[2])
redis.call('HDEL', KEYS[1], ARGV[1])
return 1
"""

@dataclass(frozen=True)
class Reservation:
    key: str
    field: str
    units: int

def _units(value) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Cost must be finite and non-negative")
    return int((amount * UNITS_PER_USD).to_integral_value(rounding=ROUND_CEILING))

def token_cost(input_tokens: int, output_tokens: int) -> Decimal:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be non-negative")
    return (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000

def check_budget(estimated_cost: float = 0) -> Reservation:
    now = datetime.now(timezone.utc)
    key = f"{settings.redis_key_prefix}:budget:{now:%Y-%m-%d}"
    expiry = int((now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)).timestamp())
    reservation = Reservation(key, "request:" + uuid.uuid4().hex, _units(estimated_cost))
    allowed = redis_client.r.eval(RESERVE, 1, key, _units(settings.daily_budget_usd),
                                  reservation.units, reservation.field, expiry)
    if not allowed:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return reservation

def release_budget(reservation: Reservation) -> None:
    redis_client.r.eval(SETTLE, 1, reservation.key, reservation.field, 0)

def record_cost(input_tokens: int, output_tokens: int,
                reservation: Reservation | None = None) -> float:
    cost = token_cost(input_tokens, output_tokens)
    units = _units(cost)
    if reservation is None:
        reservation = check_budget(estimated_cost=cost)
    if units > reservation.units:
        raise ValueError("Actual cost exceeded its reservation")
    redis_client.r.eval(SETTLE, 1, reservation.key, reservation.field, units)
    return float(cost)
