import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b2_rag_audit import run_b2
from agentledger.ingestion import load_whowhen_log
from agentledger.providers import LLMProvider, MockProvider

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


class _BareNumberProvider(LLMProvider):
    def _generate_impl(self, prompt: str) -> str:
        return "0"


def test_b2_runs_end_to_end_with_mock_provider():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b2(run, MockProvider())
    assert prediction.run_id == "run_001"
    assert prediction.agent  # non-empty
    assert isinstance(prediction.step, int)


def test_b2_falls_back_to_unknown_when_reply_is_valid_json_but_not_a_dict():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b2(run, _BareNumberProvider())
    assert prediction.agent == "unknown"
    assert prediction.step == -1


def test_b2_only_sees_retrieved_candidates_not_the_whole_log():
    """distinguishes B2 from B0: the prompt must be built from retrieve_candidates(), not the
    full event list, for a short log where not every event is in the candidate shortlist."""
    import agentledger.baselines.b2_rag_audit as b2mod

    captured = {}

    class _CapturingProvider(LLMProvider):
        def _generate_impl(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return '{"agent": "unknown", "step": -1}'

    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    run_b2(run, _CapturingProvider())
    from agentledger.agents.retriever import retrieve_candidates

    candidate_ids = {e.event_id for e in retrieve_candidates(run)}
    all_ids = {e.event_id for e in run.events}
    assert "Candidate records:" in captured["prompt"]
    for eid in candidate_ids:
        assert eid in captured["prompt"]
    # if the candidate set is a strict subset, confirm an excluded event id is also excluded
    # from the prompt (otherwise this run_001 fixture doesn't actually test the distinction)
    excluded = all_ids - candidate_ids
    if excluded:
        assert next(iter(excluded)) not in captured["prompt"]
