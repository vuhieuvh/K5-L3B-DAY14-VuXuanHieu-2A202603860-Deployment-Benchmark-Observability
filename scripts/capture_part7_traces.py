"""Retain Jaeger v3 OTLP traces that match actual archived LLM JSON logs."""
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/part7"
HTTP = build_opener(ProxyHandler({}))


def capture():
    target = OUT / "selected-traces-for-report.json"
    if target.exists():
        print("Preserving already captured trace/log pairs")
        return json.loads(target.read_text(encoding="utf-8"))
    slow, errors = {}, {}
    for path in OUT.glob("*before-agent-logs.txt"):
        with path.open(encoding="utf-8", errors="replace") as source:
            for line in source:
                if "{" not in line:
                    continue
                try:
                    entry = json.loads(line[line.index("{"):])
                except ValueError:
                    continue
                trace_id = entry.get("trace_id")
                if not trace_id:
                    continue
                if entry.get("event") == "llm_call" and entry.get("llm_ms", 0) > 1200:
                    slow[trace_id] = entry
                elif entry.get("event") == "llm_error":
                    errors[trace_id] = entry
    result = {}
    for label, candidates in [("slow", sorted(slow.values(), key=lambda e: e["llm_ms"], reverse=True)),
                              ("error", sorted(errors.values(), key=lambda e: e["ts"], reverse=True))]:
        for entry in candidates[:40]:
            trace_id = entry["trace_id"]
            try:
                with HTTP.open(f"http://127.0.0.1:16686/api/v3/traces/{trace_id}", timeout=15) as response:
                    raw = json.loads(response.read())
            except HTTPError as error:
                if error.code == 404:
                    continue  # expired/incomplete batch; try another real observed trace ID
                raise
            spans = []
            for resource in raw.get("result", {}).get("resourceSpans", []):
                for scope in resource.get("scopeSpans", []):
                    for span in scope.get("spans", []):
                        spans.append({"name": span["name"], "span_id": span["spanId"],
                                      "parent_id": span.get("parentSpanId"),
                                      "duration_ms": (int(span["endTimeUnixNano"]) - int(span["startTimeUnixNano"])) / 1e6,
                                      "status": span.get("status", {}), "events": span.get("events", []),
                                      "attributes": span.get("attributes", [])})
            if not spans:
                continue
            if label == "error" and not any(e["name"] == "exception" for s in spans for e in s["events"]):
                continue
            (OUT / f"jaeger-{label}-trace-v3.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            root_span = next(s for s in spans if not s["parent_id"])
            child = max((s for s in spans if s["parent_id"]), key=lambda s: s["duration_ms"])
            # The pipeline wrapper spans contain child spans; identify the slowest leaf step.
            parent_ids = {s["parent_id"] for s in spans}
            leaf = max((s for s in spans if s["span_id"] not in parent_ids), key=lambda s: s["duration_ms"])
            result[label] = {"trace_id": trace_id, "root_duration_ms": root_span["duration_ms"],
                             "slowest_leaf": leaf, "spans": spans, "matching_logs": [entry],
                             "selection": "Slowest matching retained LLM-call candidate, not an exhaustive global maximum" if label == "slow" else "Recent error trace with exception event and matching LLM error log"}
            break
        if label not in result:
            raise RuntimeError(f"No valid {label} trace/log pair found")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {"trace_id": v["trace_id"], "root_ms": v["root_duration_ms"],
                            "slowest_leaf": v["slowest_leaf"]["name"],
                            "leaf_ms": v["slowest_leaf"]["duration_ms"]} for k, v in result.items()}, indent=2))
    return result


if __name__ == "__main__":
    capture()
