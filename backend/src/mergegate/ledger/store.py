from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mergegate.models import LedgerEntry, Run


class LedgerStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._jsonl = self.root / "ledger.jsonl"
        self._last_hash = "GENESIS"

    def append(
        self, run_id: str, event_type: str, payload: dict[str, Any]
    ) -> LedgerEntry:
        seq = sum(1 for _ in self._iter_lines())
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest_input = f"{self._last_hash}:{canonical}".encode()
        entry_hash = hashlib.sha256(digest_input).hexdigest()
        entry = LedgerEntry(
            seq=seq,
            run_id=run_id,
            ts=datetime.now(tz=UTC),
            type=event_type,
            payload=payload,
            prev_hash=self._last_hash,
            hash=entry_hash,
        )
        with self._jsonl.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
        self._last_hash = entry_hash
        return entry

    def list_for_run(self, run_id: str) -> list[LedgerEntry]:
        return [e for e in self.read_all() if e.run_id == run_id]

    def read_all(self) -> list[LedgerEntry]:
        entries: list[LedgerEntry] = []
        for line in self._iter_lines():
            entries.append(LedgerEntry.model_validate_json(line))
        return entries

    def _iter_lines(self):
        if not self._jsonl.exists():
            return
        with self._jsonl.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield line


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = LedgerStore(root / "ledger")
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> Run:
        self._runs[run.id] = run
        path = self.root / f"{run.id}.json"
        path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        return run

    def get(self, run_id: str) -> Run | None:
        if run_id in self._runs:
            return self._runs[run_id]
        path = self.root / f"{run_id}.json"
        if not path.exists():
            return None
        run = Run.model_validate_json(path.read_text(encoding="utf-8"))
        self._runs[run_id] = run
        return run
