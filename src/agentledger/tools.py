"""Initial tool interfaces (B8). Phase 1 implements these directly over the
normalised RunLog and IntegrityLedger; the Retriever/Auditor agents that call
them as agent tools are Phase 2 work.
"""
from __future__ import annotations

from .controls import check_control as _check_control
from .ledger import IntegrityLedger
from .schema import Event, RunLog


def read_span(run: RunLog, event_id: str) -> Event | None:
    """Return one event by id, or None if it is not in this run."""
    return run.event_by_id(event_id)


def search_log(run: RunLog, query: str) -> list[Event]:
    """Naive keyword search over event content. Replaced by embedding search in Phase 2."""
    q = query.lower()
    return [e for e in run.events if q in e.content.lower()]


def get_provenance(ledger: IntegrityLedger, event_id: str) -> list[dict]:
    """Return the ledger entries up to and including the one for this event id."""
    chain = []
    for entry in ledger.entries:
        chain.append(entry.payload)
        if entry.payload.get("event_id") == event_id:
            break
    return chain


def verify_chain(ledger: IntegrityLedger) -> tuple[bool, int | None]:
    """Recompute the hash chain; see ledger.IntegrityLedger.verify for details."""
    return ledger.verify()


def check_control(control_id: str, run: RunLog, ledger: IntegrityLedger):
    """Evaluate one control-catalogue predicate against a run and its ledger."""
    return _check_control(control_id, run, ledger)
