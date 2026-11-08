import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b0_single_call import run_b0
from agentledger.ingestion import load_whowhen_log
from agentledger.providers import LLMProvider, MockProvider

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


class _BareNumberProvider(LLMProvider):
    """returns valid JSON that isn't a dict, e.g. a model replying with a bare number --
    reproduces the "'int' object is not subscriptable" crash found in a full-184 run."""

    def _generate_impl(self, prompt: str) -> str:
        return "0"


def test_b0_runs_end_to_end_with_mock_provider():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b0(run, MockProvider())
    assert prediction.run_id == "run_001"
    assert prediction.agent  # non-empty
    assert isinstance(prediction.step, int)


def test_b0_mock_provider_flags_the_error_turn():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b0(run, MockProvider())
    # run_001's error keyword is in the uploader's step-3 turn
    assert prediction.agent == "Uploader"
    assert prediction.step == 3


def test_b0_falls_back_to_unknown_when_reply_is_valid_json_but_not_a_dict():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b0(run, _BareNumberProvider())
    assert prediction.agent == "unknown"
    assert prediction.step == -1
