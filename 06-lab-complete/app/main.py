"""Part 6 agent: Redis shared state, JSON logs, Uvicorn-managed SIGTERM."""
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError
from app.auth import verify_api_key
from app.config import settings
from app import redis_client
from app.cost_guard import check_budget, record_cost, release_budget, token_cost
from app.rate_limiter import check_rate_limit
from utils.mock_llm import MOCK_RESPONSES, ask as llm_ask

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"ts": datetime.now(timezone.utc).isoformat(),
                   "lvl": record.levelname, "event": record.getMessage()}
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=False)

logger = logging.getLogger("day14.agent")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
START_TIME = time.monotonic()
# Two mock tokens per word; not real provider usage.
MAX_MOCK_OUTPUT_TOKENS = max(len(text.split()) * 2
                             for texts in MOCK_RESPONSES.values() for text in texts)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    yield
    # Uvicorn drains requests before lifespan shutdown. Keep its signal handlers.
    redis_client.r.close()
    logger.info("shutdown_complete")

app = FastAPI(title="Production AI Agent", lifespan=lifespan)

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, strict=True)
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=200)

@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.monotonic()
    request_id = uuid.uuid4().hex
    response = await call_next(request)
    route = request.scope.get("route")
    logger.info("request", extra={"fields": {
        "request_id": request_id, "method": request.method,
        "path": getattr(route, "path", "unmatched"), "status": response.status_code,
        "ms": round((time.monotonic() - started) * 1000, 3)}})
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, error: RedisError):
    logger.warning("redis_unavailable")
    return JSONResponse(status_code=503, content={"detail": "Dependency unavailable"})

@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logger.error("request_failed")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": round(time.monotonic() - START_TIME, 3)}

@app.get("/ready")
def ready():
    if not redis_client.redis_healthy():
        raise HTTPException(status_code=503, detail="Dependency unavailable")
    return {"ready": True}

@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    input_tokens = len(body.question.split()) * 2
    reservation = check_budget(estimated_cost=token_cost(input_tokens, MAX_MOCK_OUTPUT_TOKENS))
    try:
        answer = llm_ask(body.question)
    except Exception:
        release_budget(reservation)
        raise
    cost = record_cost(input_tokens, len(answer.split()) * 2, reservation)
    logger.info("mock_usage", extra={"fields": {"cost_usd": cost, "simulated": True}})
    return {"question": body.question, "answer": answer,
            "usage": {"cost_usd": cost, "simulated": True}}
