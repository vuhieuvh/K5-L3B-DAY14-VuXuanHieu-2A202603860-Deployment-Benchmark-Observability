"""Collect Part 5 health, SIGTERM, 3-replica and shared-session evidence in WSL2.

Start the k5-day14-scaling Compose stack before running this script.
"""
import http.client
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "part5"
PROD = ROOT / "05-scaling-reliability" / "production"
HTTP = build_opener(ProxyHandler({}))


def call(port, path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                  headers={"Content-Type": "application/json"} if data else {})
    try:
        response = HTTP.open(req, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        return {"path": path, "status": response.code,
                "headers": dict(response.headers), "body": json.loads(response.read())}


def develop_test():
    port = 8006
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("Port 8006 already used")
    env = dict(os.environ, PORT=str(port), PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with (OUT / "develop-server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "app.py"],
                                cwd=ROOT / "05-scaling-reliability" / "develop",
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while True:
                if proc.poll() is not None:
                    raise RuntimeError("Develop server exited; see log")
                try:
                    if call(port, "/ready")["status"] == 200:
                        break
                except (URLError, OSError):
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("Develop server startup")
                time.sleep(0.2)
            health, ready = call(port, "/health"), call(port, "/ready")
            assert health["status"] == ready["status"] == 200
            sent = threading.Event()

            def long_request():
                start = time.monotonic()
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
                try:
                    conn.request("POST", "/ask?question=hello")
                    sent.set()
                    resp = conn.getresponse()
                    return {"status": resp.status, "body": json.loads(resp.read()),
                            "elapsed_seconds": round(time.monotonic() - start, 6)}
                finally:
                    conn.close()

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(long_request)
                if not sent.wait(timeout=5):
                    raise TimeoutError("Request not sent")
                time.sleep(0.5)
                pending = not future.done()
                wchan = Path(f"/proc/{proc.pid}/wchan").read_text().strip()
                if not pending or "nanosleep" not in wchan:
                    raise AssertionError(f"Could not confirm blocking mock request: pending={pending}, wchan={wchan}")
                signal_start = time.monotonic()
                proc.send_signal(signal.SIGTERM)
                response = future.result(timeout=15)
                exit_code = proc.wait(timeout=15)
                shutdown_seconds = round(time.monotonic() - signal_start, 6)
            assert response["status"] == 200 and exit_code == 0
            return {"port": port, "health": health, "ready": ready,
                    "shutdown": {"signal": "SIGTERM", "request_pending_at_signal": pending,
                                 "process_wchan_at_signal": wchan, "response": response,
                                 "exit_code": exit_code, "seconds_from_signal_to_exit": shutdown_seconds}}
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)


def scaling_test():
    compose = ["docker", "compose", "-p", "k5-day14-scaling"]
    deadline = time.monotonic() + 90
    while True:
        ps = subprocess.run(compose + ["ps", "--format", "json"], cwd=PROD,
                            capture_output=True, text=True, check=True)
        raw = ps.stdout.strip()
        rows = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines() if line]
        agents = [r for r in rows if r.get("Service") == "agent"]
        if len(agents) == 3 and all(r.get("Health") == "healthy" for r in agents):
            break
        if time.monotonic() > deadline:
            raise TimeoutError("Three healthy agents not ready")
        time.sleep(1)
    (OUT / "compose-ps.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    text_ps = subprocess.run(compose + ["ps"], cwd=PROD, capture_output=True, text=True, check=True)
    (OUT / "compose-ps.txt").write_text(text_ps.stdout, encoding="utf-8")
    env = dict(os.environ, BASE_URL="http://127.0.0.1:18085", PYTHONIOENCODING="utf-8")
    official = subprocess.run([sys.executable, "test_stateless.py"], cwd=PROD, env=env,
                              capture_output=True, text=True, timeout=60)
    (OUT / "test-stateless.txt").write_text(official.stdout + official.stderr, encoding="utf-8")
    assert official.returncode == 0
    # Independently verify actual data: the supplied script prints success without assertions.
    turns, session_id = [], None
    questions = ["What is Docker?", "Why containers?", "What is Kubernetes?",
                 "How does load balancing work?", "What is Redis used for?"]
    for question in questions:
        result = call(18085, "/chat", "POST", {"question": question, "session_id": session_id})
        assert result["status"] == 200 and result["body"]["storage"] == "redis"
        if session_id is None:
            session_id = result["body"]["session_id"]
        assert result["body"]["session_id"] == session_id
        turns.append(result)
    history = call(18085, f"/chat/{session_id}/history")
    assert history["status"] == 200 and history["body"]["count"] == 10
    assert [m["content"] for m in history["body"]["messages"] if m["role"] == "user"] == questions
    instances = sorted({t["body"]["served_by"] for t in turns})
    assert len(instances) > 1
    health, ready = call(18085, "/health"), call(18085, "/ready")
    assert health["status"] == ready["status"] == 200
    assert health["body"]["redis_connected"] is True
    return {"base_url": env["BASE_URL"], "replicas": len(agents),
            "official_script_exit_code": official.returncode, "health": health,
            "ready": ready, "turns": turns, "history": history,
            "instances_seen": instances, "instance_failure_tested": False}


def main():
    if os.name != "posix":
        raise RuntimeError("Run in WSL2 Linux")
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {"run_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                "platform": platform.platform(), "python": platform.python_version(),
                "develop": develop_test()}
    # Preserve completed shutdown evidence even if the Compose test fails.
    (OUT / "health-shutdown.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence["scaling"] = scaling_test()
    (OUT / "results.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shutdown": evidence["develop"]["shutdown"],
                      "replicas": evidence["scaling"]["replicas"],
                      "instances_seen": evidence["scaling"]["instances_seen"],
                      "history_count": evidence["scaling"]["history"]["body"]["count"]}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
