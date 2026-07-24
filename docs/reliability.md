# Reliability behavior

MergeGate validates ten reliability scenarios in
`backend/tests/integration/test_reliability.py`: two-attempt recovery, invalid
commands, harness timeout, human rejection, manual stop, protected-file policy,
attempt exhaustion, contradiction handling, client refresh, and backend
restart.

## Backend restart limitation

The v1 workflow and active-run registry is process-local. A backend restart
does not resume an in-progress run: a subsequent request for its run ID returns
an explicit `404` message naming this limitation instead of implying that the
run succeeded or is still progressing. The prior process cannot reclassify the
lost run as `SUCCESS`.

The per-run SQLite and JSONL ledgers are written beneath a temporary
process-owned directory, but v1 does not reopen or re-index those files after a
restart. Operators must treat an interrupted run as undelivered and start a new
run from the unchanged base repository. Durable cross-process recovery remains
future work; it must persist the run registry, contracts, event cursor, and
orchestrator checkpoint together before claiming resume support.
