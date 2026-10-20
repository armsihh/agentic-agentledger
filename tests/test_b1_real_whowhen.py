"""smoke test against the real who&when benchmark in the reference repo. skips
if that sibling folder isn't present.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b1_whowhen_reference import run_b1
from agentledger.ingestion import load_whowhen_release_dir
from agentledger.providers import MockProvider

REFERENCE_DIR = Path(__file__).resolve().parent.parent.parent / "reference-Agents_Failure_Attribution"
HANDCRAFTED_DIR = REFERENCE_DIR / "Who&When" / "Hand-Crafted"

pytestmark = pytest.mark.skipif(
    not HANDCRAFTED_DIR.exists(),
    reason="reference-Agents_Failure_Attribution not cloned next to this project",
)


def test_ingests_real_handcrafted_records():
    runs = load_whowhen_release_dir(HANDCRAFTED_DIR, is_handcrafted=True, limit=5)
    assert len(runs) == 5
    for run in runs:
        assert run.events
        assert run.ground_truth is not None


def test_b1_runs_on_a_real_record():
    runs = load_whowhen_release_dir(HANDCRAFTED_DIR, is_handcrafted=True, limit=1)
    pred = run_b1(runs[0], MockProvider(), "all_at_once")
    assert pred.agent
    assert pred.step >= -1
