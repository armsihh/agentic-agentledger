"""sha-256 hash-chained, append-only ledger of normalised events (gap 2)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

GENESIS_HASH = "0" * 64


def _hash_entry(prev_hash: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


@dataclass
class LedgerEntry:
    index: int
    prev_hash: str
    hash: str
    payload: dict[str, Any]


@dataclass
class IntegrityLedger:
    entries: list[LedgerEntry] = field(default_factory=list)

    @property
    def head_hash(self) -> str:
        return self.entries[-1].hash if self.entries else GENESIS_HASH

    def append(self, payload: dict[str, Any]) -> LedgerEntry:
        prev_hash = self.head_hash
        entry = LedgerEntry(
            index=len(self.entries),
            prev_hash=prev_hash,
            hash=_hash_entry(prev_hash, payload),
            payload=payload,
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, int | None]:
        """recompute every hash in order. returns (ok, index_of_first_break)."""
        prev_hash = GENESIS_HASH
        for entry in self.entries:
            if entry.prev_hash != prev_hash:
                return False, entry.index
            if _hash_entry(entry.prev_hash, entry.payload) != entry.hash:
                return False, entry.index
            prev_hash = entry.hash
        return True, None

    def to_dicts(self) -> list[dict[str, Any]]:
        return [
            {"index": e.index, "prev_hash": e.prev_hash, "hash": e.hash, "payload": e.payload}
            for e in self.entries
        ]
