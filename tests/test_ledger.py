import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.ledger import IntegrityLedger


def test_empty_ledger_verifies():
    ledger = IntegrityLedger()
    ok, break_index = ledger.verify()
    assert ok and break_index is None


def test_chain_verifies_after_appends():
    ledger = IntegrityLedger()
    ledger.append({"event_id": "e0"})
    ledger.append({"event_id": "e1"})
    ledger.append({"event_id": "e2"})
    ok, break_index = ledger.verify()
    assert ok and break_index is None


def test_tamper_is_detected():
    ledger = IntegrityLedger()
    ledger.append({"event_id": "e0"})
    ledger.append({"event_id": "e1"})
    ledger.append({"event_id": "e2"})

    # Tamper with the middle entry's payload without recomputing its hash.
    ledger.entries[1].payload["event_id"] = "tampered"

    ok, break_index = ledger.verify()
    assert not ok
    assert break_index == 1


def test_deleted_entry_breaks_the_chain():
    ledger = IntegrityLedger()
    ledger.append({"event_id": "e0"})
    ledger.append({"event_id": "e1"})
    ledger.append({"event_id": "e2"})

    del ledger.entries[1]
    for i, entry in enumerate(ledger.entries):
        entry.index = i

    ok, break_index = ledger.verify()
    assert not ok
    assert break_index == 1
