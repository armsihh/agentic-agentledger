import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.ingestion import load_logs_from_dir
from agentledger.ledger import GENESIS_HASH, IntegrityLedger, _hash_entry
from agentledger.orchestrator import run_system
from agentledger.providers import MockProvider
from agentledger.provenance import ProvenanceGraph, build_provenance_ledger, verify_with_anchor
from agentledger.reviewer import render_report

DATA = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def _run():
    return load_logs_from_dir(DATA)[0]


def test_clean_ledger_verifies_with_anchor():
    l = build_provenance_ledger(_run())
    assert verify_with_anchor(l, l.head_hash, len(l.entries)) == (True, "ok")


def test_content_edit_is_detected():
    l = build_provenance_ledger(_run())
    l.entries[1].payload["content"] += "x"
    assert not l.verify()[0]


def test_graph_has_prov_relations_and_lineage():
    run = _run()
    g = ProvenanceGraph.from_ledger(build_provenance_ledger(run))
    rels = {r for r, _, _ in g.edges}
    assert {"wasAttributedTo", "wasDerivedFrom", "used", "wasInformedBy"} <= rels
    last = run.events[-1].event_id
    assert run.events[0].event_id in g.lineage(last)
    assert g.check_consistency() == []


def test_index_only_tamper_is_detected():
    l = build_provenance_ledger(_run())
    l.entries[1].index = 9
    assert not l.verify()[0]


def test_truncation_needs_anchor():
    l = build_provenance_ledger(_run())
    head, n = l.head_hash, len(l.entries)
    del l.entries[-1]
    assert l.verify()[0]  # bare chain cannot see it
    assert not verify_with_anchor(l, head, n)[0]


def test_rehash_attack_needs_anchor():
    l = build_provenance_ledger(_run())
    head, n = l.head_hash, len(l.entries)
    l.entries[0].payload["content"] += "x"
    prev = GENESIS_HASH
    for e in l.entries:
        e.prev_hash, e.hash = prev, _hash_entry(prev, e.payload)
        prev = e.hash
    assert l.verify()[0]
    assert not verify_with_anchor(l, head, n)[0]


def test_reviewer_report_contents():
    run = _run()
    l = build_provenance_ledger(run)
    text = render_report(run_system(run, MockProvider(), l), ledger=l)
    assert "AUDIT REPORT" in text and "INTACT" in text and "Control checks" in text
    l2 = copy.deepcopy(l)
    l2.entries[0].payload["agent"] = "evil"
    assert "TAMPERED" in render_report([], ledger=l2)
