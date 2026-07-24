"""Enumerations shared by the MergeGate domain models.

Values are taken verbatim from `specs/001-mergegate-control-plane/data-model.md`
and spec.md FR-025, including the mixed casing (non-terminal run states are
lowercase; terminal states are upper snake case) so the wire format matches
the design docs exactly.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    """Non-terminal and terminal states a Run can be in (FR-025)."""

    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_GATE = "awaiting_gate"
    SUCCESS = "SUCCESS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    EXHAUSTED = "EXHAUSTED"
    NO_PROGRESS = "NO_PROGRESS"
    TIMED_OUT = "TIMED_OUT"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CANCELLED = "CANCELLED"


class ContractMode(StrEnum):
    """How a Contract's criteria were produced (FR-001a)."""

    USER_DEFINED = "user_defined"
    AGENT_GENERATED = "agent_generated"
    HYBRID = "hybrid"


class CriterionType(StrEnum):
    """Acceptance criterion kinds (FR-001c)."""

    COMMAND = "command"
    METRIC = "metric"
    OPENAPI = "openapi"
    GIT_POLICY = "git_policy"
    DATABASE_ASSERTION = "database_assertion"
    ARCHITECTURE = "architecture"


class PassFail(StrEnum):
    """Baseline/result expectation used for red-before/green-after (FR-009)."""

    PASS = "pass"
    FAIL = "fail"


class CheckStep(StrEnum):
    """Ordered acceptance pipeline steps."""

    BUILD = "build"
    LINT = "lint"
    EXISTING_TESTS = "existing_tests"
    NEW_TESTS = "new_tests"
    MIGRATION = "migration"
    COVERAGE = "coverage"
    API_CONTRACT = "api_contract"
    POLICY = "policy"


class NodeType(StrEnum):
    """Workflow node kinds (FR-026a); values match `workflow.schema.json`."""

    INPUT = "Input"
    AGENT = "Agent"
    COMMAND = "Command"
    VALIDATOR = "Validator"
    DECISION = "Decision"
    HUMAN_GATE = "HumanGate"
    SUCCESS = "Success"
    STOP = "Stop"


class AgentRole(StrEnum):
    """One of the four default-loop roles a node's config may declare."""

    SUCCESS_CRITERIA = "success_criteria"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"


class EdgePath(StrEnum):
    """Edge path label (FR-026a)."""

    DEFAULT = "default"
    SUCCESS = "success"
    FAILURE = "failure"
