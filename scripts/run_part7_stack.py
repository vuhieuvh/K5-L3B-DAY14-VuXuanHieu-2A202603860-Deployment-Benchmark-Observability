"""Part 7 scale benchmarks and controlled chaos; never targets the Render app.

Leaves the local stack up for screenshots, with a marker when two alerts fire.
Call cleanup only after retaining UI screenshots and trace/log evidence.
"""
import csv
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "06-lab-complete/benchmark-observability/production"
OUT = ROOT / "reports/part7"
HTTP = build_opener(ProxyHandler({}))
COMPOSE = ["docker", "compose", "-p", "k5-day14-observability"]


def fetch(url):
    with HTTP.open(url, timeout=10) as response:
        return json.loads(response.read())


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args, label, env=None, allowed=(0,), timeout=300):
    result = subprocess.run(args, cwd=PROD, env=env, capture_output=True, text=True, timeout=timeout)
    (OUT / (label + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode not in allowed:
        raise RuntimeError(f"{label} failed, exit {result.returncode}; see log")
    return result


def wait_ready():
    deadline = time.monotonic() + 90
    while True:
        try:
            if fetch("http://127.0.0.1:18087/health")["status"] == "ok":
                return
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError("Agent readiness")
        time.sleep(1)


def alerts():
    return fetch("http://127.0.0.1:19090/api/v1/alerts")["data"]["alerts"]


def locust(label, users, duration, env=None):
    logfile = (OUT / (label + ".txt")).open("w", encoding="utf-8")
    proc = subprocess.Popen(COMPOSE + ["run", "--rm", "--no-deps", "--name", "k5-day14-obs-" + label,
        "locust", "-f", "/mnt/locust/locustfile.py", "--host", "http://nginx",
        "--headless", "-u", str(users), "-r", "10", "-t", f"{duration}s",
        "--csv", "/mnt/results/" + label], cwd=PROD, env=env, stdout=logfile, stderr=subprocess.STDOUT)
    return proc, logfile


def wait_load(proc, logfile):
    try:
        code = proc.wait(timeout=360)
        if code not in (0, 1):
            raise RuntimeError(f"Locust crashed: {code}")
        return code
    finally:
        logfile.close()


def configure(label, env, replicas=3):
    start = time.monotonic()
    run(COMPOSE + ["logs", "--no-color", "agent"], label + "-before-agent-logs", env=env)
    run(COMPOSE + ["up", "-d", "--scale", f"agent={replicas}", "--wait", "--wait-timeout", "90"],
        label + "-configure", env=env)
    wait_ready()
    return start


def experiment(label, changes, duration, users=30, pause=False):
    env = {**os.environ, "AGENT_VERSION": "v2", "LLM_MODEL": "mock-llm-small",
           "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", **changes}
    before = alerts()
    started = configure(label, env)
    paused_id = None
    if pause:
        ids = run(COMPOSE + ["ps", "-q", "agent"], label + "-agent-ids", env).stdout.split()
        paused_id = ids[0]
        run(["docker", "pause", paused_id], label + "-pause", env)
        started = time.monotonic()
    proc, logfile = locust(label, users, duration, env)
    observations, first_firing = [], {}
    initial_firing = sorted({a["labels"]["alertname"] for a in before if a["state"] == "firing"})
    try:
        while proc.poll() is None:
            snapshot = alerts()
            elapsed = round(time.monotonic() - started, 3)
            observations.append({"seconds_since_config_start": elapsed, "alerts": snapshot})
            firing = {a["labels"]["alertname"] for a in snapshot if a["state"] == "firing"}
            for name in firing:
                first_firing.setdefault(name, elapsed)
            if len(firing) >= 2:
                save("alerts-two-firing-latest.json", {"experiment": label, "elapsed": elapsed, "alerts": snapshot})
                if not (OUT / "alerts-screenshot-ready.json").exists():
                    save("alerts-screenshot-ready.json", {"experiment": label, "elapsed": elapsed,
                         "message": "At least two real alerts firing; capture Prometheus /alerts while load continues."})
                    print("SCREENSHOT_READY: two or more firing alerts", flush=True)
            time.sleep(5)
        code = wait_load(proc, logfile)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=30)
            logfile.close()
        if paused_id:
            run(["docker", "unpause", paused_id], label + "-unpause", env)
    result = {"changes": changes, "duration_s": duration, "users": users,
              "initial_firing": initial_firing, "first_observed_firing_seconds": first_firing,
              "timing_origin": "before compose up; for pause experiment, immediately before load after pause",
              "observations": observations, "locust_exit_code": code, "paused_container": paused_id}
    save(label + ".json", result)
    print(f"{label}: firing {first_firing}, initial {initial_firing}", flush=True)
    return result


def retain_traces():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from capture_part7_traces import capture
    capture()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    default_env = dict(os.environ, AGENT_VERSION="v2", LLM_MODEL="mock-llm-small",
                       MOCK_ERROR_RATE="0.01", MOCK_SLOW_RATE="0.03")
    resource = subprocess.run(["docker", "info", "--format", "{{json .}}"], capture_output=True, text=True, check=True)
    info = json.loads(resource.stdout)
    save("docker-resources.json", {k: info.get(k) for k in ["ServerVersion", "NCPU", "MemTotal", "OperatingSystem", "Architecture"]})
    for replicas in [1, 3]:
        label = "scale_" + str(replicas)
        configure(label, default_env, replicas)
        time.sleep(15)  # DNS service discovery refresh; specified in the lab.
        proc, log = locust(label, 100, 120, default_env)
        code = wait_load(proc, log)
        run(COMPOSE + ["ps"], label + "-ps", default_env)
        ids = run(COMPOSE + ["ps", "-q", "agent"], label + "-agent-ids", default_env).stdout.split()
        if len(ids) != replicas:
            raise AssertionError(f"Expected {replicas} agent containers, found {len(ids)}")
        print(f"{label}: exit {code}, CSV retained", flush=True)
    run(["docker", "run", "--rm", "-v", str(PROD / "prometheus") + ":/p:ro",
         "--entrypoint", "promtool", "prom/prometheus:v3.16.0", "test", "rules", "/p/alert_rules_test.yml"], "promtool")
    experiment("chaos_AB", {"MOCK_ERROR_RATE": "0.2", "MOCK_SLOW_RATE": "0.3"}, 190)
    experiment("chaos_C", {"LLM_MODEL": "mock-llm-large"}, 160)
    experiment("chaos_D", {}, 80, pause=True)
    experiment("chaos_E", {"AGENT_VERSION": "v1"}, 80)
    retain_traces()
    # Restore v2/fault defaults; keep temporary load for final UI screenshots.
    configure("restore", default_env)
    save("stack-finished.json", {"at": datetime.now(timezone.utc).isoformat(),
         "note": "Experiments done; stack remains up for UI screenshots. No instance left paused."})
    print("STACK_EXPERIMENTS_DONE", flush=True)


if __name__ == "__main__":
    main()
