"""Retain final logs then stop only the isolated Part 7 Compose project."""
import json
import subprocess
from datetime import datetime, timezone

from run_part7_stack import COMPOSE, OUT, run, save


def main():
    ids = run(COMPOSE + ["ps", "-aq"], "cleanup-container-ids").stdout.split()
    if ids:
        containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
        save("cleanup-before.json", [{"id": c["Id"], "name": c["Name"], "state": c["State"]} for c in containers])
        for container in containers:
            assert container["Config"]["Labels"]["com.docker.compose.project"] == "k5-day14-observability"
            if container["State"].get("Paused"):
                run(["docker", "unpause", container["Id"]], "cleanup-unpause-" + container["Id"][:12])
        run(COMPOSE + ["logs", "--no-color", "agent"], "final-agent-logs")
    save("stack-finished.json", {"at": datetime.now(timezone.utc).isoformat(),
         "note": "All four chaos records, selected trace/log pairs and screenshots retained; finishing stack cleanup."})
    run(COMPOSE + ["down", "-v"], "cleanup-down")
    remaining = run(COMPOSE + ["ps", "-aq"], "cleanup-after").stdout.strip()
    assert not remaining, "Part 7 containers still present"
    save("cleanup-result.json", {"at": datetime.now(timezone.utc).isoformat(),
         "project": "k5-day14-observability", "remaining_containers": [],
         "scope": "Only this local lab Compose project and its declared volumes"})
    print("Part 7 stack stopped; retained evidence remains on disk.")


if __name__ == "__main__":
    main()
