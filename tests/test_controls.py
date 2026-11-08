import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.controls import check_control
from agentledger.ingestion import load_whowhen_log
from agentledger.ledger import IntegrityLedger
from agentledger.schema import Event, RunLog, ToolCall

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
        check_control("CTRL-04", run, ledger)
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass


def test_ctrl_03_passes_when_no_high_risk_tool_calls():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    result = check_control("CTRL-03", run, ledger)
    assert result.passed


def test_ctrl_03_fails_without_prior_approval():
    run = RunLog(
        run_id="r1",
        source_format="synthetic",
        events=[
            Event(event_id="r1-0", run_id="r1", step_index=0, agent="A", role="agent", content="starting task"),
            Event(
                event_id="r1-1",
                run_id="r1",
                step_index=1,
                agent="A",
                role="agent",
                content="deleting record",
                tool_calls=[ToolCall(name="delete", arguments={"id": 1})],
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-03", run, ledger)
    assert not result.passed


def test_ctrl_03_passes_with_prior_approval():
    run = RunLog(
        run_id="r2",
        source_format="synthetic",
        events=[
            Event(event_id="r2-0", run_id="r2", step_index=0, agent="A", role="agent", content="user approved the deletion"),
            Event(
                event_id="r2-1",
                run_id="r2",
                step_index=1,
                agent="A",
                role="agent",
                content="deleting record",
                tool_calls=[ToolCall(name="delete", arguments={"id": 1})],
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-03", run, ledger)
    assert result.passed


def test_ctrl_07_fails_when_no_corrective_action_after_error():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    result = check_control("CTRL-07", run, ledger)
    assert not result.passed


def test_ctrl_07_passes_when_corrective_action_follows_error():
    run = RunLog(
        run_id="r3",
        source_format="synthetic",
        events=[
            Event(event_id="r3-0", run_id="r3", step_index=0, agent="A", role="agent", content="an error occurred during upload"),
            Event(event_id="r3-1", run_id="r3", step_index=1, agent="A", role="agent", content="retried and the issue is now fixed"),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-07", run, ledger)
    assert result.passed


def test_ctrl_11_fails_on_sensitive_tool_arguments():
    run = RunLog(
        run_id="r4",
        source_format="synthetic",
        events=[
            Event(
                event_id="r4-0",
                run_id="r4",
                step_index=0,
                agent="A",
                role="agent",
                content="logging in",
                tool_calls=[ToolCall(name="auth", arguments={"password": "hunter2"})],
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-11", run, ledger)
    assert not result.passed


def test_ctrl_11_passes_on_run_001():
    run = load_whowhen_log(SAMPLE_DIR / "run_001.json")
    ledger = _build_ledger(run)
    result = check_control("CTRL-11", run, ledger)
    assert result.passed


def test_ctrl_07_ignores_known_framework_noise_as_an_error_trigger():
    run = RunLog(
        run_id="r8",
        source_format="synthetic",
        events=[
            Event(
                event_id="r8-0", run_id="r8", step_index=0, agent="A", role="agent",
                content="All done.\nUserWarning: Resolved model mismatch: Model mapping may be incorrect.",
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-07", run, ledger)
    assert result.passed
    assert "no error step detected" in result.evidence


def test_ctrl_07_passes_on_a_same_step_self_correction():
    run = RunLog(
        run_id="r9",
        source_format="synthetic",
        events=[
            Event(
                event_id="r9-0", run_id="r9", step_index=0, agent="A", role="agent",
                content="There was an error in the formatting. Let's reformat the answer correctly.",
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-07", run, ledger)
    assert result.passed


def test_ctrl_07_recognises_try_again_as_corrective():
    run = RunLog(
        run_id="r10",
        source_format="synthetic",
        events=[
            Event(event_id="r10-0", run_id="r10", step_index=0, agent="A", role="agent", content="NameError: x is not defined"),
            Event(event_id="r10-1", run_id="r10", step_index=1, agent="A", role="agent", content="Let's try again with the import added this time."),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-07", run, ledger)
    assert result.passed


def test_ctrl_06_vacuously_passes_with_no_tool_calls():
    run = RunLog(
        run_id="r5",
        source_format="synthetic",
        events=[Event(event_id="r5-0", run_id="r5", step_index=0, agent="A", role="agent", content="just talking")],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-06", run, ledger)
    assert result.passed


def test_ctrl_06_fails_when_a_tool_call_has_no_recorded_result():
    run = RunLog(
        run_id="r6",
        source_format="synthetic",
        events=[
            Event(
                event_id="r6-0",
                run_id="r6",
                step_index=0,
                agent="A",
                role="agent",
                content="running a search",
                tool_calls=[ToolCall(name="search", arguments={"q": "x"}, result=None)],
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-06", run, ledger)
    assert not result.passed


def test_ctrl_06_passes_when_every_tool_call_has_a_recorded_result():
    run = RunLog(
        run_id="r7",
        source_format="synthetic",
        events=[
            Event(
                event_id="r7-0",
                run_id="r7",
                step_index=0,
                agent="A",
                role="agent",
                content="running a search",
                tool_calls=[ToolCall(name="search", arguments={"q": "x"}, result="3 hits")],
            ),
        ],
    )
    ledger = _build_ledger(run)
    result = check_control("CTRL-06", run, ledger)
    assert result.passed
