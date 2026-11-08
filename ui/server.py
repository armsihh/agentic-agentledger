"""AgentLedger web UI -- one local server covering the whole project (stdlib only, no new deps).

    python ui/server.py                 ->  http://127.0.0.1:8000
    python ui/server.py --port 8080 --whowhen-root "../reference-Agents_Failure_Attribution/Who&When"

what it exposes (all backed by the real code in src/agentledger and the files in results/):
    Audit        run the full pipeline (Retriever -> Auditor -> Verifier -> Policy Checker, ledger-gated)
                 on any run, with the E5 ablation switches, optional injected tampering, the provenance
                 graph with hashes, and the step-by-step trajectory log
    Tamper lab   run the Gap 2 tamper-injection harness live on a chosen data source
    Results      gap-resolution table, per-tamper-type table, Gap 1 / Gap 3 / E6 numbers from results/*.json
    Docs         browse every write-up in results/ and docs/

the offline MockProvider is the default, so the UI works with no API key; pick "live" to use whichever of
GROQ_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY is set (read from the environment or a local .env).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import run_tamper_test as tt  # noqa: E402  (reuses the exact tamper operations the harness uses)
from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full  # noqa: E402
from agentledger.ledger import _hash_entry  # noqa: E402
from agentledger.orchestrator import run_system_with_trace  # noqa: E402
from agentledger.provenance import ProvenanceGraph, build_provenance_ledger  # noqa: E402
from agentledger.providers import MockProvider, get_default_provider  # noqa: E402

REAL_ROOT = Path(os.environ.get("WHOWHEN_ROOT", ROOT.parent / "reference-Agents_Failure_Attribution" / "Who&When"))
_cache: dict[str, list] = {}

TAMPER_DESC = {
    "edit_content": "change a message's text",
    "edit_agent": "change which agent wrote an entry",
    "edit_tool_result": "forge a tool call's result (needs a log with tool calls)",
    "edit_provenance_link": "rewrite a provenance link",
    "edit_last_entry": "edit the final entry",
    "delete_middle": "remove an entry from the middle",
    "delete_first": "remove the first entry",
    "reorder_swap": "swap two adjacent entries",
    "insert_forged": "insert a forged entry",
    "renumber_only": "change only an entry's index",
    "truncate_tail": "delete the last entry (chain stays valid)",
    "edit_rechain": "edit an entry, then recompute every later hash",
    "delete_rechain": "delete an entry, then recompute every later hash",
}


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


def get_runs(source: str) -> list:
    if source not in _cache:
        if source == "sample":
            _cache[source] = load_logs_from_dir(ROOT / "data" / "sample_logs")
        elif source == "injected":
            _cache[source] = load_logs_from_dir(ROOT / "data" / "injected_violations")
        elif source == "real":
            _cache[source] = load_whowhen_release_full(REAL_ROOT) if REAL_ROOT.exists() else []
        else:
            raise ValueError(f"unknown source {source}")
    return _cache[source]


def graph_json(ledger, max_events: int) -> dict:
    """nodes/edges with layout + hashes for the client to draw. marks the first broken entry."""
    ok, bad = ledger.verify()
    entries = ledger.entries[:max_events]
    nodes, edges, ids = [], [], set()

    def add(nid, typ, x, y, label, sub=None, bad_flag=False, w=76):
        ids.add(nid)
        nodes.append({"id": nid, "type": typ, "x": x, "y": y, "label": label, "sub": sub or [], "bad": bad_flag, "w": w})

    agents = []
    for e in entries:
        a = e.payload.get("prov", {}).get("attributed_to", "agent:?")
        if a not in agents:
            agents.append(a)
    for i, a in enumerate(agents):
        add(a, "agent", 110 + i * 170, 50, a.replace("agent:", "")[:16])
    for pos, e in enumerate(entries):
        p, prov = e.payload, e.payload.get("prov", {})
        x = 100 + pos * 170
        calc = _hash_entry(e.prev_hash, p)
        sub = [f"hash {e.hash[:10]}", f"prev {e.prev_hash[:10]}"]
        mismatch = calc != e.hash
        if mismatch:
            sub.append(f"calc {calc[:10]}")
        add(p.get("event_id", f"?{pos}"), "event", x, 190, f"step {p.get('step_index', pos)}", sub,
            bad_flag=(bad == pos and not ok) or mismatch, w=112)
        for j, tc in enumerate(prov.get("tool_calls", [])):
            y = 330 + j * 130
            add(tc["id"], "toolcall", x, y, tc["name"][:14])
            add(tc["input_id"], "input", x - 45, y + 80, "input", [f"sha {tc['input_digest'][:8]}"])
            if tc.get("output_id"):
                add(tc["output_id"], "output", x + 45, y + 80, "output", [f"sha {tc['output_digest'][:8]}"])
    for e in entries:
        p, prov = e.payload, e.payload.get("prov", {})
        eid = p.get("event_id")
        pairs = [("wasAttributedTo", eid, prov.get("attributed_to"))]
        if prov.get("derived_from"):
            pairs.append(("wasDerivedFrom", eid, prov["derived_from"]))
        for tc in prov.get("tool_calls", []):
            pairs += [("wasInformedBy", tc["id"], eid), ("used", tc["id"], tc["input_id"])]
            if tc.get("output_id"):
                pairs.append(("wasGeneratedBy", tc["output_id"], tc["id"]))
        edges += [{"rel": r, "from": a, "to": b} for r, a, b in pairs if a in ids and b in ids]
    try:
        g = ProvenanceGraph.from_ledger(ledger)
        stats = {"nodes": len(g.nodes), "edges": len(g.edges), "problems": g.check_consistency()}
    except Exception as exc:  # a tampered ledger can be structurally broken
        stats = {"nodes": None, "edges": None, "problems": [f"graph could not be rebuilt: {exc}"]}
    return {"nodes": nodes, "edges": edges, "shown": len(entries), "total": len(ledger.entries),
            "chain_ok": ok, "break_index": bad, "stats": stats}


def api_meta() -> dict:
    _load_dotenv()
    return {
        "sources": {
            "sample": len(get_runs("sample")),
            "injected": len(get_runs("injected")),
            "real": len(get_runs("real")),
        },
        "real_root": str(REAL_ROOT),
        "tampers": [{"name": k, "desc": TAMPER_DESC[k]} for k in tt.TAMPERS],
        "live_provider": any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")),
    }


def api_runs(source: str) -> list:
    out = []
    for i, r in enumerate(get_runs(source)):
        out.append({"index": i, "run_id": r.run_id, "events": len(r.events),
                    "ground_truth": r.ground_truth.model_dump() if r.ground_truth else None})
    return out


def api_audit(body: dict) -> dict:
    _load_dotenv()
    runs = get_runs(body.get("source", "sample"))
    run = runs[int(body.get("index", 0))]
    ledger = build_provenance_ledger(run)
    head, length = ledger.head_hash, len(ledger.entries)
    tamper_note, detection = None, None
    name = body.get("tamper") or ""
    if name:
        tampered = copy.deepcopy(ledger)
        if tt.TAMPERS[name](tampered, random.Random(int(body.get("seed", 0)))):
            ledger = tampered
            detection = tt._detect(ledger, head, length)
            tamper_note = f"applied '{name}': {TAMPER_DESC[name]}"
        else:
            tamper_note = f"'{name}' is not applicable to this run (too few events / no tool calls) -- ledger left intact"

    live = body.get("provider") == "live"
    provider = get_default_provider() if live else MockProvider()
    provider_name = type(provider).__name__
    findings, trajectory = run_system_with_trace(
        run, provider, ledger,
        use_verifier=bool(body.get("use_verifier", True)),
        use_policy_checker=bool(body.get("use_policy_checker", True)),
    )
    gt = run.ground_truth.model_dump() if run.ground_truth else None
    return {
        "run_id": run.run_id,
        "provider": provider_name,
        "provider_note": "no API key found -- live mode fell back to the offline mock" if live and provider_name == "MockProvider" else None,
        "tamper_note": tamper_note,
        "detection": detection,
        "ledger": {"entries": len(ledger.entries), "head": ledger.head_hash, "ok": ledger.verify()[0],
                   "anchor_head": head, "anchor_length": length},
        "findings": [f.__dict__ for f in findings],
        "trajectory": trajectory,
        "events": [{"id": e.event_id, "step": e.step_index, "agent": e.agent, "role": e.role,
                    "content": e.content[:400], "tool_calls": [tc.name for tc in e.tool_calls]} for e in run.events[:300]],
        "n_events": len(run.events),
        "ground_truth": gt,
        "graph": graph_json(ledger, int(body.get("max_events", 8))),
        "provider_stats": provider.stats(),
    }


def api_tamper_batch(body: dict) -> dict:
    runs = get_runs(body.get("source", "sample"))
    limit = int(body.get("limit") or 0) or len(runs)
    runs = runs[:limit]
    reps = int(body.get("reps", 1))
    rng = random.Random(int(body.get("seed", 0)))
    modes = ("chain", "chain+graph", "anchored")
    per = {t: {"applied": 0, **{m: 0 for m in modes}} for t in tt.TAMPERS}
    false_alarms = {m: 0 for m in modes}
    for run in runs:
        clean = build_provenance_ledger(run)
        for m, hit in tt._detect(copy.deepcopy(clean), clean.head_hash, len(clean.entries)).items():
            false_alarms[m] += int(hit)
        for _ in range(reps):
            for name, fn in tt.TAMPERS.items():
                t = copy.deepcopy(clean)
                if not fn(t, rng):
                    continue
                per[name]["applied"] += 1
                for m, hit in tt._detect(t, clean.head_hash, len(clean.entries)).items():
                    per[name][m] += int(hit)
    total = sum(v["applied"] for v in per.values()) or 1
    summary = {m: {"detection_rate": sum(v[m] for v in per.values()) / total, "false_alarms": false_alarms[m]} for m in modes}
    return {"n_runs": len(runs), "n_cases": total, "per_type": per, "summary": summary,
            "desc": TAMPER_DESC, "overhead": tt._overhead(runs, repeats=3)}


def _read_json(name: str):
    p = ROOT / "results" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def api_results() -> dict:
    table = ROOT / "results" / "gap_resolution_table.md"
    sysr = _read_json("system_results.json")
    return {
        "gap_table_md": table.read_text(encoding="utf-8") if table.exists() else "",
        "tamper_real": _read_json("tamper_results_real184.json"),
        "tamper_synth": _read_json("tamper_results.json"),
        "gap1_ablation": _read_json("gap1_ablation_summary.json"),
        "gap3": _read_json("gap3_policy_eval.json"),
        "b0": _read_json("baseline_b0_real20.json"),
        "b1": (_read_json("baseline_b1_real20_allatonce.json") or {}).get("all_at_once"),
        "system": {k: v for k, v in (sysr or {}).items() if k != "runs"},
        "system_runs": (sysr or {}).get("runs", []),
        "tamper_desc": TAMPER_DESC,
    }


def api_files() -> list:
    out = []
    for d in ("results", "docs"):
        for p in sorted((ROOT / d).glob("*")):
            if p.suffix in (".md", ".json"):
                out.append(f"{d}/{p.name}")
    out.insert(0, "README.md")
    return out


def api_file(name: str) -> str:
    p = (ROOT / name).resolve()
    allowed = [(ROOT / "results").resolve(), (ROOT / "docs").resolve()]
    if p != (ROOT / "README.md").resolve() and not any(a in p.parents for a in allowed):
        raise PermissionError("file not allowed")
    if p.suffix not in (".md", ".json"):
        raise PermissionError("file type not allowed")
    return p.read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (Path(__file__).parent / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/meta":
                return self._json(api_meta())
            if u.path == "/api/runs":
                return self._json(api_runs(q.get("source", "sample")))
            if u.path == "/api/results":
                return self._json(api_results())
            if u.path == "/api/files":
                return self._json(api_files())
            if u.path == "/api/file":
                return self._send(200, api_file(q["name"]).encode(), "text/plain; charset=utf-8")
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/audit":
                return self._json(api_audit(body))
            if u.path == "/api/tamper_batch":
                return self._json(api_tamper_batch(body))
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def log_message(self, fmt, *args) -> None:  # quiet
        pass


def main() -> None:
    global REAL_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--whowhen-root", default=None)
    a = ap.parse_args()
    if a.whowhen_root:
        REAL_ROOT = Path(a.whowhen_root).resolve()
    print(f"AgentLedger UI on http://127.0.0.1:{a.port}   (real Who&When root: {REAL_ROOT}, exists={REAL_ROOT.exists()})")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
