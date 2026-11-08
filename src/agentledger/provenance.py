"""provenance graph (gap 2): PROV-style links between ledger entries and the agent, tool call,
input and output each one came from.

design: the links live *inside* each ledger entry's payload (under the "prov" key), so the same
sha-256 chain that protects the event content also protects the provenance links -- editing a
link is exactly as detectable as editing the content. `ProvenanceGraph.from_ledger()` rebuilds
the graph from a ledger, so the graph is never a second, separately-trustable source of truth.

PROV mapping (W3C PROV-DM vocabulary):
    agent      prov:Agent     the agent that produced the event            node  "agent:<name>"
    event      prov:Entity    the logged message itself (= ledger entry)   node  event_id
    toolcall   prov:Activity  one tool invocation inside the event         node  "<event_id>#tc<i>"
    input      prov:Entity    the tool call's arguments                    node  "<event_id>#tc<i>:in"
    output     prov:Entity    the tool call's result (if recorded)         node  "<event_id>#tc<i>:out"
edges:
    wasAttributedTo(event, agent)       wasGeneratedBy(output, toolcall)
    used(toolcall, input)               wasInformedBy(toolcall, event)  (the event issued the call)
    wasDerivedFrom(event, prior event)  (each event is derived from the previous one in the run)

this does not change the Event schema; it only adds links between ledger entries.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .ledger import IntegrityLedger
from .schema import Event, RunLog


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def event_payload(event: Event, prev_event_id: str | None) -> dict[str, Any]:
    """full-event ledger payload + provenance links.

    unlike a payload of just (event_id, agent, tool_calls), this covers *every* field of the
    event (content, role, step_index, timestamp), so editing a message's text breaks the chain.
    """
    toolcalls = []
    for i, tc in enumerate(event.tool_calls):
        tc_id = f"{event.event_id}#tc{i}"
        toolcalls.append(
            {
                "id": tc_id,
                "name": tc.name,
                "input_id": f"{tc_id}:in",
                "input_digest": _digest(tc.arguments),
                # None when the log never recorded a result (that absence is itself CTRL-06 evidence)
                "output_id": f"{tc_id}:out" if tc.result is not None else None,
                "output_digest": _digest(tc.result) if tc.result is not None else None,
            }
        )
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "step_index": event.step_index,
        "agent": event.agent,
        "role": event.role,
        "content": event.content,
        "timestamp": event.timestamp,
        "tool_calls": [tc.model_dump() for tc in event.tool_calls],
        "prov": {
            "attributed_to": f"agent:{event.agent}",
            "derived_from": prev_event_id,
            "tool_calls": toolcalls,
        },
    }


def build_provenance_ledger(run: RunLog) -> IntegrityLedger:
    """hash-chain every event of a run, with provenance links, into a fresh ledger."""
    ledger = IntegrityLedger()
    prev: str | None = None
    for event in run.events:
        ledger.append(event_payload(event, prev))
        prev = event.event_id
    return ledger


@dataclass
class ProvenanceGraph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> {"type", "ledger_index", "ledger_hash"?}
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (relation, source, target)

    @classmethod
    def from_ledger(cls, ledger: IntegrityLedger) -> "ProvenanceGraph":
        g = cls()
        for entry in ledger.entries:
            p = entry.payload
            prov = p.get("prov")
            if not isinstance(prov, dict):
                continue
            eid = p.get("event_id")
            g.nodes[eid] = {"type": "event", "ledger_index": entry.index, "ledger_hash": entry.hash}
            g.nodes.setdefault(prov["attributed_to"], {"type": "agent"})
            g.edges.append(("wasAttributedTo", eid, prov["attributed_to"]))
            if prov.get("derived_from") is not None:
                g.edges.append(("wasDerivedFrom", eid, prov["derived_from"]))
            for tc in prov.get("tool_calls", []):
                g.nodes[tc["id"]] = {"type": "toolcall", "ledger_index": entry.index}
                g.nodes[tc["input_id"]] = {"type": "input", "ledger_index": entry.index}
                g.edges.append(("wasInformedBy", tc["id"], eid))
                g.edges.append(("used", tc["id"], tc["input_id"]))
                if tc.get("output_id"):
                    g.nodes[tc["output_id"]] = {"type": "output", "ledger_index": entry.index}
                    g.edges.append(("wasGeneratedBy", tc["output_id"], tc["id"]))
        return g

    def lineage(self, node_id: str) -> list[str]:
        """every node reachable from node_id following edges (what this record rests on)."""
        seen: list[str] = []
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for _rel, src, tgt in self.edges:
                if src == cur and tgt not in seen:
                    seen.append(tgt)
                    stack.append(tgt)
        return seen

    def check_consistency(self) -> list[str]:
        """structural problems in the graph itself (independent of the hash chain)."""
        problems: list[str] = []
        for rel, src, tgt in self.edges:
            if src not in self.nodes:
                problems.append(f"{rel}: unknown source {src}")
            if tgt not in self.nodes:
                problems.append(f"{rel}: unknown target {tgt}")
            if rel == "wasDerivedFrom" and src in self.nodes and tgt in self.nodes:
                if self.nodes[tgt].get("ledger_index", 0) >= self.nodes[src].get("ledger_index", 0):
                    problems.append(f"wasDerivedFrom: {src} derived from {tgt}, which is not earlier in the ledger")
        return problems


def verify_with_anchor(
    ledger: IntegrityLedger, anchor_head: str | None = None, anchor_length: int | None = None
) -> tuple[bool, str]:
    """chain check, plus optional external anchor (head hash + length recorded at write time).

    a bare hash chain cannot see (a) truncation of the tail or (b) a full re-hash by someone who
    can rewrite every entry; both are only visible against a head hash/length held somewhere the
    attacker cannot also rewrite. returns (ok, reason).
    """
    ok, idx = ledger.verify()
    if not ok:
        return False, f"chain break at index {idx}"
    if anchor_length is not None and len(ledger.entries) != anchor_length:
        return False, f"length {len(ledger.entries)} != anchored {anchor_length}"
    if anchor_head is not None and ledger.head_hash != anchor_head:
        return False, "head hash differs from anchor"
    problems = ProvenanceGraph.from_ledger(ledger).check_consistency()
    if problems:
        return False, "provenance graph inconsistent: " + problems[0]
    return True, "ok"
