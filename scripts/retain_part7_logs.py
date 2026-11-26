"""Retain actual logs for each generation of local lab agent containers."""
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/part7"
streams = {}
try:
    deadline = time.monotonic() + 1000
    while time.monotonic() < deadline:
        result = subprocess.run(["docker", "ps", "-q",
            "--filter", "label=com.docker.compose.project=k5-day14-observability",
            "--filter", "label=com.docker.compose.service=agent"], capture_output=True, text=True, check=True)
        for container in result.stdout.split():
            if container not in streams:
                log = (OUT / f"archive-{container}-before-agent-logs.txt").open("w", encoding="utf-8")
                proc = subprocess.Popen(["docker", "logs", "--follow", container], stdout=log, stderr=subprocess.STDOUT)
                streams[container] = (proc, log)
        if (OUT / "stack-finished.json").exists():
            break
        time.sleep(2)
finally:
    for proc, log in streams.values():
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        log.close()
