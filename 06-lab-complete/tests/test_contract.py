"""Behavior tests using real FastAPI requests and an isolated Redis database.

TEST_REDIS_URL must point to the disposable test Redis, never production.
"""
import json
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

os.environ["AGENT_API_KEY"] = secrets.token_urlsafe(32)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:18086/15")

from fastapi.testclient import TestClient
from app.config import settings
from app.main import app


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = {"X-API-Key": settings.agent_api_key}

    def test_missing_and_wrong_keys_are_401(self):
        for headers in ({}, {"X-API-Key": "wrong-demo-key"}):
            self.assertEqual(self.client.post("/ask", headers=headers,
                                             json={"question": "hello"}).status_code, 401)

    def test_valid_key_receives_answer(self):
        response = self.client.post("/ask", headers=self.headers, json={"question": "Docker"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["answer"])

    def test_whitespace_or_wrong_type_is_422(self):
        for question in ("   ", 42, None):
            response = self.client.post("/ask", headers=self.headers, json={"question": question})
            self.assertEqual(response.status_code, 422)

    def test_liveness_and_readiness(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").status_code, 200)


class RedisBehaviorTests(unittest.TestCase):
    def test_parallel_rate_requests_share_one_limit(self):
        from fastapi import HTTPException
        from app.rate_limiter import check_rate_limit
        key = secrets.token_urlsafe(32)

        def attempt(_):
            try:
                check_rate_limit(key)
                return 200
            except HTTPException as error:
                return error.status_code

        with patch.object(settings, "rate_limit_per_minute", 5):
            with ThreadPoolExecutor(max_workers=12) as pool:
                statuses = list(pool.map(attempt, range(20)))
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 15)

    def test_parallel_budget_reservations_cannot_overspend(self):
        from fastapi import HTTPException
        from app.cost_guard import check_budget, release_budget

        def reserve(_):
            try:
                return check_budget(estimated_cost=0.0006)
            except HTTPException as error:
                self.assertEqual(error.status_code, 402)
                return None

        with patch.object(settings, "redis_key_prefix", "test-" + secrets.token_hex(12)), \
             patch.object(settings, "daily_budget_usd", 0.001):
            with ThreadPoolExecutor(max_workers=8) as pool:
                reservations = list(pool.map(reserve, range(8)))
            successful = [r for r in reservations if r is not None]
            self.assertEqual(len(successful), 1)
            release_budget(successful[0])
            # Failed LLM requests must release their reservation for the next request.
            reservation = check_budget(estimated_cost=0.0006)
            release_budget(reservation)

    def test_cost_settlement_releases_unused_reserve_and_is_idempotent(self):
        from app.cost_guard import check_budget, record_cost, release_budget
        with patch.object(settings, "redis_key_prefix", "test-" + secrets.token_hex(12)), \
             patch.object(settings, "daily_budget_usd", 0.001):
            reservation = check_budget(estimated_cost=0.0009)
            # 1000 input tokens at 0.00015 USD/1K, no output.
            self.assertAlmostEqual(record_cost(1000, 0, reservation), 0.00015)
            record_cost(1000, 0, reservation)  # repeat settlement must not double-charge
            remaining = check_budget(estimated_cost=0.0008)
            release_budget(remaining)

    def test_dependency_outage_keeps_health_but_blocks_ready_and_ask(self):
        import redis
        from app import redis_client
        down = redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.1,
                              socket_timeout=0.1, decode_responses=True)
        try:
            with patch.object(redis_client, "r", down):
                client = TestClient(app, raise_server_exceptions=False)
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(client.get("/ready").status_code, 503)
                result = client.post("/ask", headers={"X-API-Key": settings.agent_api_key},
                                     json={"question": "Hello"})
                self.assertEqual(result.status_code, 503)
                self.assertNotIn("Traceback", result.text)
        finally:
            down.close()

    def test_json_logging_escapes_quotes_without_leaking_request(self):
        import io
        import logging
        from app.main import JsonFormatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("part6-formatter-test")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            logger.info('event "quotes"\nnext line')
            lines = stream.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["event"], 'event "quotes"\nnext line')
        finally:
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
