"""Run original load/eval tools and retain actual outputs (including SLO failures)."""
import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "06-lab-complete/benchmark-observability/develop"
OUT = ROOT / "reports"
LOGS = OUT / "part7"
HTTP = build_opener(ProxyHandler({}))


@contextmanager
def server(version, port, slow="0.03", errors="0.01"):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} already in use")
    env = dict(os.environ, AGENT_VERSION=version, PORT=str(port),
               MOCK_SLOW_RATE=slow, MOCK_ERROR_RATE=errors, PYTHONUNBUFFERED="1")
    with (LOGS / f"{version}-{port}-slow{slow}-error{errors}.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "app.py"], cwd=DEV, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 25
            while True:
                if proc.poll() is not None:
                    raise RuntimeError("Server exited; see log")
                try:
                    with HTTP.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("Server startup")
                time.sleep(0.2)
            yield f"http://127.0.0.1:{port}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def command(name, args):
    result = subprocess.run([sys.executable] + args, cwd=DEV, capture_output=True,
                            text=True, timeout=300)
    (LOGS / (name + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode not in (0, 1):
        raise RuntimeError(f"{name} crashed; see log")
    manifest = LOGS / "commands.jsonl"
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "args": args, "exit_code": result.returncode,
                            "at": datetime.now(timezone(timedelta(hours=7))).isoformat()}) + "\n")
    print(f"{name}: exit {result.returncode}", flush=True)
    return result.returncode


def eval_run(name, url, extra=()):
    return command(name, ["eval/run_eval.py", "--url", url, "--out", str(OUT / (name + ".json")), *extra])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baseline", "fixed"])
    phase = parser.parse_args().phase
    LOGS.mkdir(parents=True, exist_ok=True)
    if phase == "fixed":
        with server("v2", 8002, slow="0", errors="0") as url:
            code = eval_run("eval_v2_fixed", url, ["--min-accuracy", "1.0", "--baseline", str(OUT / "eval_v2.json")])
            if code:
                raise RuntimeError("Fixed quality gate failed; inspect report before changing KB")
        return
    if (OUT / "eval_v2.json").exists():
        raise RuntimeError("Baseline already saved; do not overwrite pre-fix evidence")
    (LOGS / "environment.json").write_text(json.dumps({
        "at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "meminfo": Path("/proc/meminfo").read_text(),
        "note": "Load tests: default mock errors0.01; eval: errors0, slow0 to isolate quality. Mock costs only."}, indent=2), encoding="utf-8")
    for version, port in [("v1", 8001), ("v2", 8002)]:
        with server(version, port, slow="0", errors="0") as url:
            extra = ["--baseline", str(OUT / "eval_v1.json")] if version == "v2" else []
            eval_run("eval_" + version, url, extra)
    with server("v2", 8002) as url:
        with HTTP.open(url + "/metrics") as response:
            (LOGS / "metrics-initial.txt").write_bytes(response.read())
        for concurrency in [1, 10, 50, 100]:
            name = f"load_v2_c{concurrency}"
            command(name, ["load_test.py", "--url", url, "--requests", "300",
                           "--concurrency", str(concurrency), "--out", str(OUT / (name + ".json"))])
    for slow in ["0", "0.03", "0.1"]:
        with server("v2", 8002, slow=slow) as url:
            name = "load_v2_slow_" + slow
            command(name, ["load_test.py", "--url", url, "--requests", "300", "--concurrency", "20",
                           "--out", str(OUT / (name + ".json"))])


if __name__ == "__main__":
    main()
