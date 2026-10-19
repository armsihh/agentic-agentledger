import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.controls import check_control
from agentledger.ingestion import load_whowhen_log
from agentledger.ledger import IntegrityLedger

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


def test_ctrl_01_passes_on_a_complete_untampered_ledger():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    result = check_control("CTRL-01", run, ledger)
    assert result.passed


def test_ctrl_01_fails_on_a_tampered_ledger():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    ledger.entries[0].payload["agent"] = "tampered"
    result = check_control("CTRL-01", run, ledger)
    assert not result.passed


def test_ctrl_02_passes_when_every_tool_call_is_ledgered():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    result = check_control("CTRL-02", run, ledger)
    assert result.passed


def test_unimplemented_control_raises_not_implemented():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    try:
        check_control("CTRL-03", run, ledger)
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
