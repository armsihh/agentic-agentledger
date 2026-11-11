"""render a run's provenance graph as a self-contained HTML/SVG file (no dependencies).

usage:
    python eval/visualize_provenance.py                                   (data/sample_logs run 0)
    python eval/visualize_provenance.py --index 1 --out results/prov_run2.html
    python eval/visualize_provenance.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --index 3 --max-events 8
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full
from agentledger.provenance import ProvenanceGraph, build_provenance_ledger

COL = {"agent": "#c2410c", "event": "#1d4ed8", "toolcall": "#7e22ce", "input": "#15803d", "output": "#0e7490"}
EDGE = {"wasAttributedTo": "#c2410c", "wasDerivedFrom": "#1d4ed8", "wasInformedBy": "#7e22ce",
        "used": "#15803d", "wasGeneratedBy": "#0e7490"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="data/sample_logs")
    ap.add_argument("--real-whowhen-root", default=None)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--max-events", type=int, default=12)
    ap.add_argument("--out", default="results/provenance_graph.html")
    a = ap.parse_args()

    runs = load_whowhen_release_full(a.real_whowhen_root) if a.real_whowhen_root else load_logs_from_dir(ROOT / a.logs)
    run = runs[a.index]
    run = run.model_copy(update={"events": run.events[: a.max_events]})
    ledger = build_provenance_ledger(run)
    g = ProvenanceGraph.from_ledger(ledger)

    # layout: agents row y=50, events row y=190, toolcalls y=330, input/output y=450
    pos: dict[str, tuple[float, float]] = {}
    agents = sorted(n for n, v in g.nodes.items() if v["type"] == "agent")
    for i, n in enumerate(agents):
        pos[n] = (110 + i * 170, 50)
    step = 170
    toolcalls = {}
    for e in ledger.entries:
        x = 100 + e.index * step
        pos[e.payload["event_id"]] = (x, 190)
        for j, tc in enumerate(e.payload["prov"]["tool_calls"]):
            tx = x + j * 0
            pos[tc["id"]] = (tx, 330 + j * 130)
            pos[tc["input_id"]] = (tx - 45, 410 + j * 130)
            if tc["output_id"]:
                pos[tc["output_id"]] = (tx + 45, 410 + j * 130)
    width = max(900, 180 + len(ledger.entries) * step, 160 + len(agents) * 170)
    height = max(520, max(y for _, y in pos.values()) + 60)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%">']
    for rel, s, t in g.edges:
        if s in pos and t in pos:
            (x1, y1), (x2, y2) = pos[s], pos[t]
            dashed = ' stroke-dasharray="5 4"' if rel == "wasDerivedFrom" else ""
            parts.append(f'<path d="M{x1},{y1} Q{(x1+x2)/2},{(y1+y2)/2-(35 if rel=="wasDerivedFrom" else 0)} {x2},{y2}" '
                         f'fill="none" stroke="{EDGE[rel]}" stroke-width="1.5" opacity=".7"{dashed}/>')
    entry_by_event = {e.payload["event_id"]: e for e in ledger.entries}
    digests = {}
    for e in ledger.entries:
        for tc in e.payload["prov"]["tool_calls"]:
            digests[tc["input_id"]] = tc["input_digest"]
            if tc["output_id"]:
                digests[tc["output_id"]] = tc["output_digest"]
    for n, (x, y) in pos.items():
        typ = g.nodes[n]["type"]
        label = n.split("#")[-1] if typ != "event" else f"step {n.rsplit('-', 1)[-1]}"
        if typ == "agent":
            label = n.replace("agent:", "")
        label = label[:18]
        sub = []  # extra hash lines drawn inside the node
        if typ == "event":
            ent = entry_by_event[n]
            sub = [f"hash {ent.hash[:10]}", f"prev {ent.prev_hash[:10]}"]
        elif n in digests:
            sub = [f"sha {digests[n][:8]}"]
        h = 28 + 13 * len(sub)
        w = 112 if typ == "event" else 76
        parts.append(f'<rect x="{x-w/2}" y="{y-14}" width="{w}" height="{h}" rx="6" fill="{COL[typ]}" opacity=".15" stroke="{COL[typ]}"/>'
                     f'<text x="{x}" y="{y+4}" text-anchor="middle" font-size="11" fill="{COL[typ]}">{html.escape(label)}</text>')
        for k, line in enumerate(sub):
            parts.append(f'<text x="{x}" y="{y+18+13*k}" text-anchor="middle" font-size="9" font-family="monospace" fill="{COL[typ]}">{line}</text>')
    parts.append("</svg>")

    legend = "".join(f'<span style="color:{c}">&#9632; {k}</span> ' for k, c in COL.items())
    legend2 = "".join(f'<span style="color:{c}">&#8212; {k}</span> ' for k, c in EDGE.items())
    ok = ledger.verify()[0]
    doc = (f"<!doctype html><meta charset=utf-8><title>Provenance graph {html.escape(run.run_id[:20])}</title>"
           "<body style='font-family:system-ui;margin:24px;max-width:1200px'>"
           f"<h2>Provenance graph — run {html.escape(run.run_id[:40])}</h2>"
           f"<p>{len(ledger.entries)} ledger entries, {len(g.nodes)} nodes, {len(g.edges)} edges. "
           f"Chain verifies: {ok}. Head hash: <code>{ledger.head_hash[:16]}…</code></p>"
           f"<p>{legend}<br>{legend2} (dashed = derived-from). Each event's <code>prev</code> equals the previous event's <code>hash</code> — that is the chain.</p>" + "".join(parts) + "</body>")
    out = ROOT / a.out
    out.write_text(doc, encoding="utf-8")
    print(f"Wrote {out}  ({len(g.nodes)} nodes, {len(g.edges)} edges)")


if __name__ == "__main__":
    main()
