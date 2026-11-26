"""Read-only checks of retained submission evidence; does not rerun benchmarks."""
import csv
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/part7"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    names = [f"load_v2_c{n}.json" for n in (1, 10, 50, 100)]
    names += [f"load_v2_slow_{n}.json" for n in ("0", "0.03", "0.1")]
    names += [f"eval_{n}.json" for n in ("v1", "v2", "v2_fixed")]
    develop = ROOT / "06-lab-complete/benchmark-observability/develop"
    for name in names:
        assert read(ROOT / "reports" / name) == read(develop / "reports" / name), name
    final = read(ROOT / "reports/eval_v2_fixed.json")
    assert final["total"] == final["passed"] == 23 and final["errors"] == 0
    commands = [json.loads(line) for line in (OUT / "commands.jsonl").read_text().splitlines()]
    exits = {c["name"]: c["exit_code"] for c in commands}
    assert exits["eval_v2_fixed"] == 0 and exits["eval_v1_regression"] == 1

    for n in (1, 3):
        name = f"scale_{n}_stats.csv"
        original = ROOT / "06-lab-complete/benchmark-observability/production/benchmark-results" / name
        copied = ROOT / "benchmark-results" / name
        assert copied.read_bytes() == original.read_bytes()
        with copied.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        ask = next(r for r in rows if r["Name"] == "/ask")
        print(f"scale {n}: {ask['Request Count']} requests, {ask['Failure Count']} failures, "
              f"RPS={ask['Requests/s']}, p95={ask['95%']} ms")
    screenshots = ["dashboard", "running", "test", "grafana-dashboard", "jaeger-slow-trace",
                   "jaeger-error-trace", "prometheus-alert-firing"]
    for name in screenshots:
        with Image.open(ROOT / "screenshots" / (name + ".png")) as screenshot:
            assert screenshot.format == "PNG" and min(screenshot.size) >= 300
            screenshot.verify()

    firing = read(OUT / "alerts-screenshot-state.json")["data"]["alerts"]
    firing = sorted({a["labels"]["alertname"] for a in firing if a["state"] == "firing"})
    assert len(firing) >= 2
    for label, selected in read(OUT / "selected-traces-for-report.json").items():
        raw = read(OUT / f"jaeger-{label}-trace-v3.json")
        spans = [s for r in raw["result"]["resourceSpans"] for scope in r["scopeSpans"] for s in scope["spans"]]
        assert all(s["traceId"] == selected["trace_id"] for s in spans)
        assert any(log["trace_id"] == selected["trace_id"] for log in selected["matching_logs"])
        if label == "error":
            assert any(e["name"] == "exception" for s in spans for e in s.get("events", []))
        print(f"{label} trace/log verified: {selected['trace_id']}")
    assert "SUCCESS" in (OUT / "promtool.txt").read_text()
    for label in ("AB", "C", "D", "E"):
        result = read(OUT / f"chaos_{label}.json")
        observed = {a["labels"]["alertname"] for o in result["observations"]
                    for a in o["alerts"] if a["state"] == "firing"}
        print(f"chaos {label}: initially firing={result['initial_firing']}; observed={sorted(observed)}")
    report = (ROOT / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    assert "PENDING" not in report and "sẽ điền" not in report
    print(f"PASS: 10 JSON pairs, eval 23/23 + regression gate, scale CSVs, 7 PNGs, "
          f"trace/log pairs, promtool, {len(firing)} firing alerts, four chaos records")


if __name__ == "__main__":
    main()
