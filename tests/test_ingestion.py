import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.ingestion import load_logs_from_dir, load_whowhen_log

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def test_load_single_log():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    assert run.run_id == "run_001"
    assert run.source_format == "whowhen"
    assert len(run.events) == 5
    assert run.events[3].agent == "Uploader"
    assert run.ground_truth.responsible_agent == "Uploader"
    assert run.ground_truth.decisive_step == 3


def test_load_logs_from_dir():
    runs = load_logs_from_dir(SAMPLE_DIR)
    assert len(runs) == 3
    assert {r.run_id for r in runs} == {"run_001", "run_002", "run_003"}
