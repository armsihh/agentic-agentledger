"""initial tool interfaces (b8), implemented directly over RunLog/IntegrityLedger."""
from __future__ import annotations

from .controls import check_control as _check_control
from .ledger import IntegrityLedger
from .schema import Event, RunLog


def read_span(run: RunLog, event_id: str) -> Event | None:
    """return one event by id, or None if not in this run."""
    return run.event_by_id(event_id)


def search_log(run: RunLog, query: str) -> list[Event]:
    """naive keyword search over event content."""
    q = query.lower()
    return [e for e in run.events if q in e.content.lower()]


def get_provenance(ledger: IntegrityLedger, event_id: str) -> list[dict]:
    """ledger entries up to and including the one for this event id."""
    chain = []
    for entry in ledger.entries:
        chain.append(entry.payload)
        if entry.payload.get("event_id") == event_id:
            break
    return chain


def verify_chain(ledger: IntegrityLedger) -> tuple[bool, int | None]:
    return ledger.verify()


def check_control(control_id: str, run: RunLog, ledger: IntegrityLedger):
    return _check_control(control_id, run, ledger)
