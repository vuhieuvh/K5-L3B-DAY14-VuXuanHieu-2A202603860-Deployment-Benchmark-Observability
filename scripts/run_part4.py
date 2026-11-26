"""Collect real Part 4 HTTP evidence on Linux, with JWTs redacted.

The cost experiment uses a separate process and a deliberately tiny demo
budget. No template application file is modified; all LLM usage is mock.
"""
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "part4"
HTTP = build_opener(ProxyHandler({}))


def call(port, path, method="GET", body=None, token=None):
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if payload else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(f"http://127.0.0.1:{port}{path}", data=payload,
                  headers=headers, method=method)
    try:
        response = HTTP.open(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return {"method": method, "path": path, "status": response.code,
                "headers": dict(response.headers),
                "body": json.loads(response.read().decode())}


def expect(result, status):
    if result["status"] != status:
        raise AssertionError(f"{result['method']} {result['path']}: expected {status}, got {result['status']}")
    return result


def login(port, results):
    result = expect(call(port, "/auth/token", "POST",
                         {"username": "student", "password": "demo123"}), 200)
    token = result["body"]["access_token"]
    result["body"]["access_token"] = "[REDACTED]"
    result["body"]["hint"] = "Authorization: Bearer [REDACTED]"
    results.append(result)
    return token


@contextmanager
def server(port, budget=None):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} is already in use")
    env = dict(os.environ, JWT_SECRET=secrets.token_urlsafe(48),
               PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", ENVIRONMENT="development")
    code = "import app; import uvicorn; "
    if budget is not None:
        code += f"app.cost_guard.daily_budget_usd={budget!r}; "
    code += f"uvicorn.run(app.app, host='127.0.0.1', port={port}, log_level='info')"
    label = "jwt-rate" if budget is None else "cost-experiment"
    with (OUT / f"{label}-server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "-c", code],
                                cwd=ROOT / "04-api-gateway" / "production",
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f"Server exited; see {label}-server.log")
                try:
                    if call(port, "/health")["status"] == 200:
                        break
                except (URLError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(label)
                time.sleep(0.2)
            yield
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main():
    if os.name != "posix":
        raise RuntimeError("Run this script with the Linux Python environment in WSL2")
    import jwt
    import fastapi
    import uvicorn
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with server(8004):
        results.append(expect(call(8004, "/ask", "POST", {"question": "Hello"}), 401))
        results.append(expect(call(8004, "/auth/token", "POST",
                                   {"username": "student", "password": "wrong-demo-password"}), 401))
        token = login(8004, results)
        results.append(expect(call(8004, "/ask", "POST", {"question": "Explain JWT"}, token), 200))
        results.append(expect(call(8004, "/admin/stats", token=token), 403))
        loop = []
        for i in range(20):
            result = call(8004, "/ask", "POST", {"question": f"Test {i+1}"}, token)
            if result["status"] not in (200, 429):
                raise AssertionError(f"Unexpected rate test status: {result['status']}")
            loop.append(result)
        counts = dict(Counter(str(r["status"]) for r in loop))
        if counts.get("429", 0) == 0:
            raise AssertionError("No 429 observed")
        usage = expect(call(8004, "/me/usage", token=token), 200)
    cost = []
    with server(8005, budget=0.000001):
        token = login(8005, cost)
        cost.append(expect(call(8005, "/ask", "POST", {"question": "Hello"}, token), 200))
        cost.append(expect(call(8005, "/ask", "POST", {"question": "Hello again"}, token), 402))
        cost.append(expect(call(8005, "/me/usage", token=token), 200))
    evidence = {
        "run_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "platform": platform.platform(), "os_name": os.name,
        "python": platform.python_version(), "pyjwt": jwt.__version__,
        "fastapi": fastapi.__version__, "uvicorn": uvicorn.__version__,
        "note": "Real local HTTP, mock LLM. Costs are mock estimates, not real provider charges. JWTs and signing secrets not saved.",
        "jwt_rate_port": 8004, "jwt_results": results,
        "rate_test": {"request_count": 20, "prior_successful_ask_requests": 1,
                      "counts": counts, "responses": loop, "usage_after": usage},
        "cost_experiment": {
            "port": 8005, "daily_budget_usd": 0.000001,
            "setup": "Isolated server, set app.cost_guard.daily_budget_usd in memory before uvicorn.run. Default demo budget is 1.0; source files unchanged.",
            "responses": cost},
    }
    encoded = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    # All saved response bodies were redacted at login; credentials are not stored.
    if "eyJ" in encoded:
        raise AssertionError("Potential unredacted JWT in evidence")
    (OUT / "jwt-rate-cost-results.json").write_text(encoded, encoding="utf-8")
    print(json.dumps({"rate_counts": counts,
                      "jwt_statuses": [r["status"] for r in results],
                      "cost_statuses": [r["status"] for r in cost],
                      "evidence": str(OUT / "jwt-rate-cost-results.json")}, indent=2))


if __name__ == "__main__":
    main()
