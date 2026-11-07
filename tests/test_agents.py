import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.agents import auditor, verifier
from agentledger.agents.policy_checker import run_policy_checks
from agentledger.agents.retriever import retrieve_candidates
from agentledger.ingestion import load_whowhen_log
from agentledger.ledger import IntegrityLedger
from agentledger.orchestrator import run_system
from agentledger.providers import MockProvider

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def _build_ledger(run):
    ledger = IntegrityLedger()
    for event in run.events:
        ledger.append(
            {
                "event_id": event.event_id,
                "agent": event.agent,
                "tool_calls": [tc.model_dump() for tc in event.tool_calls],
            }
        )
    return ledger


def test_retriever_includes_the_error_step_and_is_bounded():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    candidates = retrieve_candidates(run, max_candidates=3)
    assert any(e.step_index == 3 for e in candidates)  # the "403 error" step
    assert len(candidates) <= 3


def test_auditor_propose_returns_a_parsed_claim():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    candidates = retrieve_candidates(run)
    claim = auditor.propose(run, MockProvider(), candidates)
    assert claim.run_id == run.run_id
    assert isinstance(claim.step, int)


def test_verifier_rejects_a_claim_with_no_citations():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    claim = auditor.AuditorClaim(run.run_id, "Uploader", 3, [], "no evidence given", "{}")
    result = verifier.verify(run, MockProvider(), claim)
    assert not result.verified


def test_verifier_rejects_citations_that_dont_exist():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    claim = auditor.AuditorClaim(run.run_id, "Uploader", 3, ["does-not-exist"], "bogus", "{}")
    result = verifier.verify(run, MockProvider(), claim)
    assert not result.verified


def test_policy_checker_skips_unimplemented_predicates():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    results = run_policy_checks(run, ledger)
    implemented_ids = {r.control_id for r in results if r.implemented}
    assert {"CTRL-01", "CTRL-02", "CTRL-03", "CTRL-07", "CTRL-11"} <= implemented_ids
    assert all(r.implemented or r.control_id not in implemented_ids for r in results)


def test_orchestrator_run_system_returns_gap1_and_control_findings():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    findings = run_system(run, MockProvider(), ledger, use_verifier=True, use_policy_checker=True)
    assert findings[0].control_id is None  # the Gap-1 attribution finding comes first
    control_findings = [f for f in findings if f.control_id is not None]
    assert len(control_findings) >= 5  # the five implemented predicates


def test_orchestrator_ablation_flags_shrink_the_output():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    findings = run_system(run, MockProvider(), ledger, use_verifier=False, use_policy_checker=False)
    assert len(findings) == 1
    assert findings[0].control_id is None


def test_orchestrator_flags_broken_ledger_as_unverified():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    ledger.entries[0].payload["agent"] = "tampered"
    findings = run_system(run, MockProvider(), ledger, use_verifier=False, use_policy_checker=False)
    assert findings[0].verified is False
