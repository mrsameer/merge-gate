from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TerminalState(StrEnum):
    SUCCESS = "SUCCESS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    EXHAUSTED = "EXHAUSTED"
    NO_PROGRESS = "NO_PROGRESS"
    TIMED_OUT = "TIMED_OUT"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    AWAITING_GATE = "awaiting_gate"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_FINAL_GATE = "awaiting_final_gate"
    SUCCESS = TerminalState.SUCCESS
    CLARIFICATION_REQUIRED = TerminalState.CLARIFICATION_REQUIRED
    HUMAN_REJECTED = TerminalState.HUMAN_REJECTED
    EXHAUSTED = TerminalState.EXHAUSTED
    NO_PROGRESS = TerminalState.NO_PROGRESS
    TIMED_OUT = TerminalState.TIMED_OUT
    POLICY_BLOCKED = TerminalState.POLICY_BLOCKED
    CANCELLED = TerminalState.CANCELLED


class NodeType(StrEnum):
    INPUT = "Input"
    AGENT = "Agent"
    COMMAND = "Command"
    VALIDATOR = "Validator"
    DECISION = "Decision"
    HUMAN_GATE = "HumanGate"
    SUCCESS = "Success"
    STOP = "Stop"


class AgentRole(StrEnum):
    SUCCESS_CRITERIA = "success_criteria"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"


class CriterionType(StrEnum):
    COMMAND = "command"
    METRIC = "metric"
    OPENAPI = "openapi"
    GIT_POLICY = "git_policy"
    DATABASE_ASSERTION = "database_assertion"
    ARCHITECTURE = "architecture"


class ExpectedResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class CheckStep(StrEnum):
    BUILD = "build"
    LINT = "lint"
    EXISTING_TESTS = "existing_tests"
    NEW_TESTS = "new_tests"
    MIGRATION = "migration"
    COVERAGE = "coverage"
    API_CONTRACT = "api_contract"
    POLICY = "policy"


class Budget(BaseModel):
    max_attempts: int = 3
    max_wall_clock_s: int = 3600
    max_model_calls: int = 20


class CostAccounting(BaseModel):
    model_calls: int = 0
    tokens: int = 0
    usd: float = 0.0
    wall_clock_s: float = 0.0


class Criterion(BaseModel):
    id: str
    type: CriterionType
    priority: int = 0
    command: str | None = None
    expected_exit_code: int | None = 0
    baseline_expected: ExpectedResult | None = None
    result_expected: ExpectedResult | None = ExpectedResult.PASS
    metric_path: str | None = None
    minimum: float | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Contract(BaseModel):
    id: str
    run_id: str
    mode: str = "hybrid"
    criteria: list[Criterion] = Field(default_factory=list)
    approved: bool = False
    frozen_hash: str | None = None


class CheckResult(BaseModel):
    criterion_id: str
    step: CheckStep
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    baseline_result: ExpectedResult | None = None


class AcceptanceInput(BaseModel):
    commit_sha: str
    validation_config: dict[str, Any]
    tool_versions: dict[str, str]
    env_fingerprint: str


class Verdict(BaseModel):
    attempt_id: str
    passed: bool
    checks: list[CheckResult] = Field(default_factory=list)
    acceptance_hash: str = ""
    acceptance_input: AcceptanceInput | None = None
    replay_of: str | None = None


class StructuredFeedback(BaseModel):
    criterion: str
    command: str
    exit_code: int
    failure_signature: str
    first_failing_location: str
    attempt: int


class Attempt(BaseModel):
    id: str
    run_id: str
    index: int
    worktree_path: str = ""
    branch: str = ""
    diff: str = ""
    changed_files: list[str] = Field(default_factory=list)
    harness_log: str = ""
    verdict: Verdict | None = None
    failure_signature: str | None = None
    feedback: StructuredFeedback | None = None


class Run(BaseModel):
    id: str
    workflow_id: str
    objective: str
    repo_ref: str
    status: RunStatus = RunStatus.AWAITING_GATE
    budgets: Budget = Field(default_factory=Budget)
    attempts: list[Attempt] = Field(default_factory=list)
    current_attempt: int = 0
    cost: CostAccounting = Field(default_factory=CostAccounting)
    contract: Contract | None = None
    branch_ref: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class Policy(BaseModel):
    protected_paths: list[str] = Field(default_factory=list)
    forbidden_diff_patterns: list[str] = Field(default_factory=list)


class NodeConfig(BaseModel):
    role: AgentRole | None = None
    instructions: str | None = None
    provider: str | None = None
    model: str | None = None
    tools: list[str] = Field(default_factory=list)
    command: str | None = None
    timeout_s: int | None = None
    criteria_ref: str | None = None
    retry_limit: int | None = None
    completion_condition: str | None = None
    success_path: str | None = None
    failure_path: str | None = None


class Node(BaseModel):
    id: str
    type: NodeType
    name: str
    config: NodeConfig = Field(default_factory=NodeConfig)


class Edge(BaseModel):
    id: str | None = None
    source: str
    target: str
    path: str = "default"


class Workflow(BaseModel):
    id: str
    name: str
    version: str | None = None
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    budgets: Budget | None = None


class LedgerEntry(BaseModel):
    seq: int
    run_id: str
    ts: datetime
    type: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str
