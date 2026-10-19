import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b0_single_call import run_b0
from agentledger.ingestion import load_whowhen_log
from agentledger.providers import MockProvider

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def test_b0_runs_end_to_end_with_mock_provider():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b0(run, MockProvider())
    assert prediction.run_id == "run_001"
    assert prediction.agent  # non-empty
    assert isinstance(prediction.step, int)


def test_b0_mock_provider_flags_the_error_turn():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    prediction = run_b0(run, MockProvider())
    # run_001's error keyword ("error") is in the Uploader's step-3 turn.
    assert prediction.agent == "Uploader"
    assert prediction.step == 3
