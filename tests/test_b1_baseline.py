import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b1_whowhen_reference import run_b1
from agentledger.ingestion import load_whowhen_log
from agentledger.providers import MockProvider

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def test_all_at_once_runs_end_to_end():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    pred = run_b1(run, MockProvider(), "all_at_once")
    assert pred.method == "all_at_once"
    assert pred.agent == "Uploader"
    assert pred.step == 3


def test_step_by_step_runs_end_to_end():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    pred = run_b1(run, MockProvider(), "step_by_step")
    assert pred.method == "step_by_step"
    # stops at the first step with an error keyword
    assert pred.agent == "Uploader"
    assert pred.step == 3


def test_binary_search_runs_end_to_end():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    pred = run_b1(run, MockProvider(), "binary_search")
    assert pred.method == "binary_search"
    assert 0 <= pred.step < len(run.events)


def test_unknown_method_raises():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    try:
        run_b1(run, MockProvider(), "not_a_method")
        assert False, "expected ValueError"
    except ValueError:
        pass
