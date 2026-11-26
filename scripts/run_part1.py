"""Run the unchanged Part 1 apps and save actual HTTP evidence (no benchmark)."""
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "part1"
BASE = "http://127.0.0.1:8000"
HTTP = build_opener(ProxyHandler({}))


def request(path, method="GET", body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = Request(BASE + path, data=payload, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        response = HTTP.open(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return {"method": method, "path": path, "request_json": body,
                "status": response.code,
                "body": json.loads(response.read().decode("utf-8"))}


def run_app(variant, cases):
    global BASE
    port = 8000 if variant == "develop" else 8001
    BASE = f"http://127.0.0.1:{port}"
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} already has a listener; stop it before running")
    command = [sys.executable, "-m", "uvicorn", "app:app",
               "--host", "127.0.0.1", "--port", str(port)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               ENVIRONMENT="development", DEBUG="false", HOST="127.0.0.1",
               PORT=str(port), OPENAI_API_KEY="", AGENT_API_KEY="")
    with (OUT / f"{variant}-server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT / "01-localhost-vs-production" / variant,
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{variant} exited; see server log")
                try:
                    if request("/")["status"] == 200:
                        break
                except (URLError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{variant} did not start")
                time.sleep(0.2)
            results = []
            for path, method, body, expected in cases:
                result = request(path, method, body)
                results.append(result)
                if result["status"] != expected:
                    raise AssertionError(result)
            return {"base_url": BASE, "command": command, "responses": results}
        finally:
            # Windows terminate is cleanup, not evidence of graceful SIGTERM handling.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    import fastapi
    import uvicorn
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {
        "run_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "platform": platform.platform(), "os_name": os.name,
        "python": platform.python_version(), "fastapi": fastapi.__version__,
        "uvicorn": uvicorn.__version__, "graceful_shutdown_tested": False,
        "note": "Real HTTP on loopback; uvicorn CLI, no reload. Mock LLM. Not a load test.",
    }
    evidence["develop"] = run_app("develop", [
        ("/", "GET", None, 200),
        ("/ask?question=Hello", "POST", None, 200),
        ("/ask", "POST", {"question": "Hello"}, 422),
        ("/health", "GET", None, 404),
    ])
    evidence["production"] = run_app("production", [
        ("/ask", "POST", {"question": "Hello"}, 200),
        ("/health", "GET", None, 200),
        ("/ready", "GET", None, 200),
        ("/ask", "POST", {}, 422),
    ])
    target = OUT / "http-results.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
