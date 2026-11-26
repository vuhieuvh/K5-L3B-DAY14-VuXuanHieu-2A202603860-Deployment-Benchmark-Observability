"""Exercise the actual Part 6 Compose stack, save sanitized evidence, clean up."""
import json
import os
import secrets
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "06-lab-complete"
OUT = ROOT / "reports" / "part6"
HTTP = build_opener(ProxyHandler({}))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    env = dict(os.environ, AGENT_API_KEY=key, REDIS_KEY_PREFIX="part6-smoke-" + secrets.token_hex(8))
    compose = ["docker", "compose", "-p", "k5-day14-part6"]

    def run(args):
        return subprocess.run(args, cwd=LAB, env=env, text=True, capture_output=True, check=True)

    def request(path, api_key=None, body=None):
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request("http://127.0.0.1:18006" + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
        try:
            response = HTTP.open(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return {"path": path, "status": response.code,
                    "body": json.loads(response.read())}

    with (OUT / "compose-up.txt").open("w", encoding="utf-8") as log:
        try:
            run(compose + ["config", "--quiet"])
            result = run(compose + ["up", "-d", "--build", "--wait", "--wait-timeout", "90"])
            log.write(result.stdout + result.stderr)
            ps = run(compose + ["ps"])
            (OUT / "compose-ps.txt").write_text(ps.stdout, encoding="utf-8")
            evidence = {"run_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                        "responses": [request("/health"), request("/ready"),
                                      request("/ask", body={"question": "Hello"}),
                                      request("/ask", "wrong-demo-key", {"question": "Hello"}),
                                      request("/ask", key, {"question": "What is Docker?"})]}
            assert [r["status"] for r in evidence["responses"]] == [200, 200, 401, 401, 200]
            container = run(compose + ["ps", "-q", "agent"]).stdout.strip()
            info = json.loads(run(["docker", "inspect", container]).stdout)[0]
            # Do not store Config.Env: it contains the random API key.
            image = json.loads(run(["docker", "image", "inspect", info["Image"]]).stdout)[0]
            uid = run(compose + ["exec", "-T", "agent", "id", "-u"]).stdout.strip()
            evidence["container"] = {"image_id": info["Image"], "image_size_bytes": image["Size"],
                                     "user": info["Config"]["User"], "uid": uid,
                                     "health": info["State"]["Health"]["Status"],
                                     "pid1_command": run(compose + ["exec", "-T", "agent", "python", "-c",
                                          "from pathlib import Path; print(Path('/proc/1/cmdline').read_bytes().replace(bytes([0]), b' ').decode())"]).stdout.strip()}
            assert uid != "0" and image["Size"] < 500 * 1024 * 1024
            assert "uvicorn" in evidence["container"]["pid1_command"]
            started = time.monotonic()
            run(compose + ["stop", "agent"])
            evidence["stop_seconds"] = round(time.monotonic() - started, 6)
            stopped = json.loads(run(["docker", "inspect", container]).stdout)[0]
            evidence["stop_exit_code"] = stopped["State"]["ExitCode"]
            assert evidence["stop_exit_code"] == 0 and evidence["stop_seconds"] < 10
            (OUT / "compose-results.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"statuses": [r["status"] for r in evidence["responses"]],
                              "image_bytes": image["Size"], "uid": uid,
                              "stop_exit_code": evidence["stop_exit_code"],
                              "stop_seconds": evidence["stop_seconds"]}))
        except subprocess.CalledProcessError as error:
            log.write(error.stdout + error.stderr)
            raise RuntimeError("Compose failed; see reports/part6/compose-up.txt") from None
        finally:
            logs = subprocess.run(compose + ["logs", "--no-color"], cwd=LAB, env=env,
                                  capture_output=True, text=True)
            (OUT / "compose-logs.txt").write_text(logs.stdout + logs.stderr, encoding="utf-8")
            down = subprocess.run(compose + ["down"], cwd=LAB, env=env, capture_output=True, text=True)
            (OUT / "compose-down.txt").write_text(down.stdout + down.stderr, encoding="utf-8")
            if down.returncode:
                raise RuntimeError("Compose cleanup failed")


if __name__ == "__main__":
    main()
