"""
===============================================================================
Governed Runtime Evolution — Research Reference Implementation
===============================================================================

Research reference implementation accompanying the paper (AS IS):

    "Governed Evolution of Agent Runtimes through Executable Operational Cognition"

-------------------------------------------------------------------------------
Purpose
-------------------------------------------------------------------------------

This repository operationalizes a governed runtime evolution architecture on top of the LangGraph/DeepAgents ecosystem.

The implementation intentionally does NOT attempt to build:
    - unrestricted autonomous self-modification,
    - AGI-like recursive autonomy,
    - a production-ready autonomous platform.

Instead, it operationalizes the paper's central thesis:

    code artifacts can become persistent operational capabilities
    under explicit governance constraints.

This implementation should be interpreted as:
    - executable reference architecture
    - architectural realization of governed runtime evolution
    - operational prototype substrate
rather than empirical validation of runtime performance claims.

-------------------------------------------------------------------------------
Architectural Separation
-------------------------------------------------------------------------------

DeepAgents / LangGraph provide:
    - orchestration
    - state handling
    - subagents
    - tool execution
    - middleware
    - runtime infrastructure

This runtime adds:
    - governed capability evolution
    - capability lifecycle management
    - persistent operational substrate
    - mutation governance
    - artifact persistence
    - validation and promotion boundaries
    - runtime introspection

-------------------------------------------------------------------------------
Conceptual Hierarchy
-------------------------------------------------------------------------------

Artifact:
    Generated operational entity:
        - prompt
        - workflow
        - skill
        - evaluator
        - routing rule
        - executable module

Capability:
    Persisted and validated artifact reusable by future runtime executions.

Operational Cognition:
    Emergent runtime behavior produced through interaction between persistent
    capabilities, governance loops, traces, evaluators and runtime memory.

-------------------------------------------------------------------------------
Core Thesis
-------------------------------------------------------------------------------

Python is not the intelligence.

Python acts as:
    - governed kernel
    - persistence substrate
    - lifecycle controller
    - audit surface
    - mutation boundary

The DeepAgent loop performs:
    - pattern detection
    - abstraction
    - capability synthesis
    - reflection
    - governance reasoning
    - operational evolution

===============================================================================
"""



# =============================================================================
# QUICK MENTAL MODEL
# =============================================================================
#
# The runtime follows the governance lifecycle proposed in the paper:
#
#     1. artifacts are generated
#     2. validation occurs
#     3. lifecycle transitions are evaluated
#     4. mutations may be proposed
#     5. governance determines promotion
#
# Only governed and validated artifacts become persistent operational
# capabilities integrated into future runtime cognition.
#
# This repository should therefore be interpreted as:
#
#     paper + executable reference architecture
#
# rather than a standalone autonomous agent framework.
#

from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
import re
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# OPTIONAL IMPORTS
# =============================================================================
#
# The file remains readable even if DeepAgents is not installed. This makes it
# suitable for architecture review, static analysis, and incremental refactoring.

DEEPAGENTS_AVAILABLE = True
LANGCHAIN_MIDDLEWARE_AVAILABLE = True
QUICKJS_AVAILABLE = True

try:
    from deepagents import create_deep_agent
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
    from deepagents.backends.utils import create_file_data
except Exception:  # pragma: no cover
    DEEPAGENTS_AVAILABLE = False
    create_deep_agent = None
    CompositeBackend = None
    StateBackend = None
    StoreBackend = None
    create_file_data = None

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore
except Exception:  # pragma: no cover
    MemorySaver = None
    InMemoryStore = None

try:
    from langchain_core.tools import tool, ToolRuntime
except Exception:  # pragma: no cover
    def tool(fn=None, **_kwargs):
        """Fallback decorator for static review without langchain-core."""
        if fn is None:
            def _decorator(f):
                return f
            return _decorator
        return fn

    class ToolRuntime:  # type: ignore
        """Fallback type for static review."""
        pass

try:
    from langchain_quickjs import CodeInterpreterMiddleware
except Exception:  # pragma: no cover
    QUICKJS_AVAILABLE = False
    CodeInterpreterMiddleware = None

try:
    from langchain.agents.middleware import (
        ModelCallLimitMiddleware,
        ModelRetryMiddleware,
        SummarizationMiddleware,
        TodoListMiddleware,
        ToolCallLimitMiddleware,
        ToolRetryMiddleware,
    )
except Exception:  # pragma: no cover
    LANGCHAIN_MIDDLEWARE_AVAILABLE = False
    ModelCallLimitMiddleware = None
    ModelRetryMiddleware = None
    SummarizationMiddleware = None
    TodoListMiddleware = None
    ToolCallLimitMiddleware = None
    ToolRetryMiddleware = None


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

logger = logging.getLogger("governed-agent-runtime")


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime_v10"

SKILLS_DIR = RUNTIME_DIR / "skills"
GENERATED_SKILLS_DIR = SKILLS_DIR / "generated"
CANONICAL_SKILLS_DIR = SKILLS_DIR / "canonical"

HARNESS_DIR = RUNTIME_DIR / "harness"
PROMPTS_DIR = HARNESS_DIR / "prompts"
POLICIES_DIR = HARNESS_DIR / "policies"
WORKFLOWS_DIR = HARNESS_DIR / "workflows"
ROUTING_RULES_DIR = HARNESS_DIR / "routing_rules"
EVALUATION_CONTRACTS_DIR = HARNESS_DIR / "evaluation_contracts"

TRACES_DIR = RUNTIME_DIR / "traces"
EVALS_DIR = RUNTIME_DIR / "evals"
MUTATIONS_DIR = RUNTIME_DIR / "mutations"
REGISTRY_DIR = RUNTIME_DIR / "registry"
REPORTS_DIR = RUNTIME_DIR / "reports"

for _directory in [
    RUNTIME_DIR,
    SKILLS_DIR,
    GENERATED_SKILLS_DIR,
    CANONICAL_SKILLS_DIR,
    HARNESS_DIR,
    PROMPTS_DIR,
    POLICIES_DIR,
    WORKFLOWS_DIR,
    ROUTING_RULES_DIR,
    EVALUATION_CONTRACTS_DIR,
    TRACES_DIR,
    EVALS_DIR,
    MUTATIONS_DIR,
    REGISTRY_DIR,
    REPORTS_DIR,
]:
    _directory.mkdir(parents=True, exist_ok=True)


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str) -> str:
    """
    Convert LLM-generated names into conservative filesystem-safe slugs.
    """
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or f"artifact_{uuid.uuid4().hex[:8]}"


def write_json(path: Path, data: Any) -> None:
    """Write JSON with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        data = data.model_dump()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    """Read JSON or return default."""
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    """Append JSON object to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


# =============================================================================
# DATA MODELS
# =============================================================================
#
# These models represent the persistent operational substrate proposed in the
# paper. Runtime evolution is intentionally mediated through explicit lifecycle
# artifacts rather than opaque hidden memory.
#
# TraceEvent:
#     Operational observations and runtime telemetry.
#
# GeneratedSkillSpec:
#     Persisted capability artifacts.
#
# HarnessMutation:
#     Governed runtime modifications.
#
# CapabilityReview:
#     Validation and governance evidence.
#
# Together they form the inspectable persistent operational substrate.

# =============================================================================

class TraceEvent(BaseModel):
    """
    Compact execution trace.

    In production this can be populated from:
        - Langfuse
        - LangSmith
        - OpenTelemetry
        - CI logs
        - sandbox execution
        - tool calls
        - deployment monitors

    V10 does not interpret traces through hardcoded pattern detection. The agent
    inspects traces and decides what they mean.
    """

    event_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:10]}")
    timestamp: str = Field(default_factory=utc_now_iso)
    event_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    success: bool | None = None
    latency_ms: float | None = None
    cost_estimate: float | None = None
    related_artifacts: list[str] = Field(default_factory=list)


class GeneratedSkillSpec(BaseModel):
    """
    Registry entry for an agent-authored DeepAgents Skill.

    The agent writes:
        - SKILL.md
        - module.py
        - tests
        - metadata

    Python persists and validates. It does not decide the skill semantics.
    """

    skill_id: str
    name: str
    description: str
    stage: Literal["experimental", "validated", "trusted", "canonical", "deprecated"] = "experimental"
    created_at: str = Field(default_factory=utc_now_iso)
    created_by: str = "runtime-evolution-agent"
    skill_dir: str
    files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Implements: HarnessMutation lifecycle model described in the paper
# (Governed Runtime Evolution / Mutation Governance sections).
class HarnessMutation(BaseModel):
    """
    Candidate self-modification of the harness.

    Mutations are stored as artifacts first. Promotion is explicit and governed.
    This prevents chaotic self-modification.
    """

    mutation_id: str = Field(default_factory=lambda: f"mutation_{uuid.uuid4().hex[:10]}")
    timestamp: str = Field(default_factory=utc_now_iso)
    target_type: Literal[
        "system_prompt",
        "policy",
        "workflow",
        "routing_rule",
        "evaluation_contract",
    ]
    target_name: str
    rationale: str
    content: str
    stage: Literal["proposed", "validated", "promoted", "rejected"] = "proposed"
    risk_level: Literal["low", "medium", "high"] = "medium"
    created_by: str = "runtime-evolution-agent"


# Implements: governance-aware validation and review artifacts discussed
# in the lifecycle and operational governance sections of the paper.
class CapabilityReview(BaseModel):
    """
    Structured review artifact.

    The LLM may create these through record_capability_review. This makes review
    another code-adjacent, inspectable artifact in the harness.
    """

    review_id: str = Field(default_factory=lambda: f"review_{uuid.uuid4().hex[:10]}")
    timestamp: str = Field(default_factory=utc_now_iso)
    artifact_id: str
    reviewer: str
    verdict: Literal["accept", "revise", "reject", "promote", "deprecate"]
    rationale: str
    evidence: dict[str, Any] = Field(default_factory=dict)


# Implements: runtime introspection surface used for operational
# observability and governance-aware runtime inspection.
class HarnessState(BaseModel):
    """
    Snapshot of the inspectable harness state.
    """

    generated_skills: list[GeneratedSkillSpec] = Field(default_factory=list)
    mutations: list[HarnessMutation] = Field(default_factory=list)
    recent_traces: list[dict[str, Any]] = Field(default_factory=list)
    active_system_prompt_files: list[str] = Field(default_factory=list)
    active_policy_files: list[str] = Field(default_factory=list)
    active_workflow_files: list[str] = Field(default_factory=list)
    active_routing_rule_files: list[str] = Field(default_factory=list)
    active_evaluation_contract_files: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now_iso)


@dataclass
class RuntimeContext:
    """
    Per-run context.

    In production, the application should supply real assistant/user/org ids.
    """

    assistant_id: str = "governed-agent-runtime"
    user_id: str = "default-user"
    org_id: str = "default-org"
    environment: str = "local"



# -----------------------------------------------------------------------------
# Knowledge-Grounded Runtime Graph Approximation
# -----------------------------------------------------------------------------
#
# The paper introduces the concept of a Knowledge-Grounded Runtime Graph.
#
# In this reference implementation, the graph is approximated through the
# interaction between:
#
#     - trace registries
#     - capability registries
#     - mutation registries
#     - lifecycle reviews
#     - runtime memory notes
#
# Collectively these artifacts form an inspectable operational lineage layer
# connecting runtime evolution, governance and persistent capabilities.
#


# =============================================================================
# GOVERNANCE POLICY MODEL
# =============================================================================
#
# Structural representation of governance constraints discussed in the paper.
#
# This intentionally remains lightweight in the reference implementation.
# In production systems this layer could evolve toward:
#     - policy engines
#     - external approval systems
#     - evaluator orchestration
#     - distributed governance services
#     - HITL approval workflows
#
# The goal here is architectural visibility rather than full enforcement logic.
#

@dataclass
class GovernancePolicy:
    allow_high_risk_mutations: bool = False
    require_validation_before_promotion: bool = True
    require_review_artifacts: bool = True
    allow_direct_prompt_mutation: bool = False
    require_audit_trail: bool = True


# =============================================================================
# REGISTRY FILES
# =============================================================================

REGISTRY_FILE = REGISTRY_DIR / "skills_registry.json"
MUTATIONS_FILE = REGISTRY_DIR / "harness_mutations.json"
REVIEWS_FILE = REGISTRY_DIR / "capability_reviews.json"
TRACE_FILE = TRACES_DIR / "trace_events.jsonl"


def load_skill_registry() -> list[GeneratedSkillSpec]:
    """Load generated skills."""
    raw = read_json(REGISTRY_FILE, [])
    return [GeneratedSkillSpec(**item) for item in raw]


def save_skill_registry(items: list[GeneratedSkillSpec]) -> None:
    """Save generated skills."""
    write_json(REGISTRY_FILE, [item.model_dump() for item in items])


def upsert_skill_registry(spec: GeneratedSkillSpec) -> None:
    """Insert or update generated skill."""
    items = load_skill_registry()
    filtered = [item for item in items if item.skill_id != spec.skill_id]
    filtered.append(spec)
    save_skill_registry(filtered)


def load_mutations() -> list[HarnessMutation]:
    """Load harness mutations."""
    raw = read_json(MUTATIONS_FILE, [])
    return [HarnessMutation(**item) for item in raw]


def save_mutations(items: list[HarnessMutation]) -> None:
    """Save harness mutations."""
    write_json(MUTATIONS_FILE, [item.model_dump() for item in items])


def upsert_mutation(mutation: HarnessMutation) -> None:
    """Insert or update harness mutation."""
    items = load_mutations()
    filtered = [item for item in items if item.mutation_id != mutation.mutation_id]
    filtered.append(mutation)
    save_mutations(filtered)


def load_reviews() -> list[CapabilityReview]:
    """Load capability reviews."""
    raw = read_json(REVIEWS_FILE, [])
    return [CapabilityReview(**item) for item in raw]


def save_reviews(items: list[CapabilityReview]) -> None:
    """Save capability reviews."""
    write_json(REVIEWS_FILE, [item.model_dump() for item in items])


def append_review(review: CapabilityReview) -> None:
    """Append capability review."""
    items = load_reviews()
    items.append(review)
    save_reviews(items)


def load_recent_traces(limit: int = 20) -> list[dict[str, Any]]:
    """Load recent trace events."""
    if not TRACE_FILE.exists():
        return []
    lines = TRACE_FILE.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:]
    out: list[dict[str, Any]] = []
    for line in selected:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# =============================================================================
# INITIAL HARNESS FILES
# =============================================================================

def ensure_initial_harness_files() -> None:
    """
    Seed editable harness specs.

    In V10 these specs are not merely config. They are self-modifiable operational
    cognition artifacts. The agent may propose new versions under governance.
    """

    system_prompt_file = PROMPTS_DIR / "system_prompt.md"
    policy_file = POLICIES_DIR / "runtime_policy.md"
    workflow_file = WORKFLOWS_DIR / "runtime_evolution_workflow.md"
    routing_file = ROUTING_RULES_DIR / "runtime_routing.md"
    eval_contract_file = EVALUATION_CONTRACTS_DIR / "skill_evaluation_contract.md"

    if not system_prompt_file.exists():
        system_prompt_file.write_text(
            textwrap.dedent(
                """
                # Governed Runtime Evolution V10 System Prompt

                You are a governed self-evolving DeepAgents runtime.

                You do not merely solve tasks. You improve the operational system
                that solves tasks.

                Your core principle:

                    Code is executable operational memory.

                Generated artifacts can become:
                    - DeepAgents skills
                    - tests
                    - evaluators
                    - workflow specs
                    - prompt refinements
                    - policies
                    - routing rules
                    - regression suites
                    - operational knowledge

                The runtime kernel exposes safe affordances. You own the cognitive
                decisions: pattern detection, abstraction, synthesis, review,
                promotion proposals, and harness improvement.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
            )

    if not policy_file.exists():
        policy_file.write_text(
            textwrap.dedent(
                """
                # Runtime Policy

                1. Generated skills start as experimental.
                2. Skills should include SKILL.md, module.py, metadata.json and tests.
                3. Promotion requires validation and evidence.
                4. High-risk changes require human approval before promotion.
                5. Prefer additive changes over destructive changes.
                6. Never mutate permission boundaries, network access, credentials,
                   deployment commands, or destructive filesystem behavior without
                   explicit approval.
                7. Treat prompt, policy, workflow, routing and evaluation changes as
                   harness mutations with lifecycle state.
                8. Avoid hardcoding cognition in Python; encode reusable cognition as
                   governed artifacts.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
            )

    if not workflow_file.exists():
        workflow_file.write_text(
            textwrap.dedent(
                """
                # Runtime Evolution Workflow

                1. Inspect traces, generated skills, policies and workflows.
                2. Decide whether observed behavior reveals a reusable pattern.
                3. If a pattern exists, create a small composable skill.
                4. Generate validation tests and metadata.
                5. Validate the skill.
                6. Record a review artifact.
                7. Promote only with evidence.
                8. If the harness itself is limiting behavior, propose a mutation.
                9. Keep risky mutations proposed until approved.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
            )

    if not routing_file.exists():
        routing_file.write_text(
            textwrap.dedent(
                """
                # Runtime Routing Rules

                Use runtime-evolution-agent when:
                - traces show repeated manual work
                - a missing validator causes repeated failures
                - a workflow is reused but not formalized
                - a task would benefit from a new reusable skill
                - the harness prompt, policy or workflow appears to be the bottleneck

                Use skill-validator-agent when:
                - a generated skill should be reviewed
                - promotion is being considered
                - tests, safety or metadata are incomplete

                Use harness-governor-agent when:
                - a mutation affects policies, permissions, routing or evaluation
                - risk level is medium or high
                """
            ).strip()
            + "\n",
            encoding="utf-8",
            )

    if not eval_contract_file.exists():
        eval_contract_file.write_text(
            textwrap.dedent(
                """
                # Skill Evaluation Contract

                A generated skill should be evaluated for:

                - syntactic validity
                - minimality
                - deterministic behavior
                - clear SKILL.md description
                - useful examples
                - tests or executable checks
                - safety boundaries
                - reusability across tasks
                - alignment with runtime policies

                Passing syntax is not enough. The agent should provide evidence
                explaining why the skill is useful operational memory.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
            )


ensure_initial_harness_files()


# =============================================================================
# VALIDATION KERNEL
# =============================================================================
#
# The paper explicitly argues against unrestricted runtime self-modification.
#
# Consequently, the kernel only implements bounded governance primitives:
#     - static validation
#     - lifecycle transitions
#     - mutation boundaries
#     - auditability
#
# Semantic cognition remains delegated to the DeepAgent runtime.

# =============================================================================
#
# V10 deliberately keeps this limited. The kernel validates safety boundaries, not
# cognitive semantics. The agent must decide what capabilities mean and why they
# are useful.

FORBIDDEN_IMPORTS = {
    "subprocess",
    "socket",
    "multiprocessing",
    "shutil",
}

FORBIDDEN_CALL_NAMES = {
    "exec",
    "eval",
    "compile",
    "__import__",
}

RISKY_TEXT_PATTERNS = [
    r"rm\s+-rf",
    r"curl\s+.*\|\s*sh",
    r"wget\s+.*\|\s*sh",
    r"pip\s+install\s+.*--trusted-host",
    r"os\.system",
]


def validate_python_module(module_code: str) -> tuple[bool, list[str]]:
    """
    Minimal static gate for generated Python.

    Not a sandbox. Use real sandbox/CI in production.
    """
    issues: list[str] = []

    try:
        tree = ast.parse(module_code)
    except SyntaxError as e:
        return False, [f"syntax_error: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    issues.append(f"forbidden_import: {alias.name}")

        if isinstance(node, ast.ImportFrom):
            module_name = (node.module or "").split(".")[0]
            if module_name in FORBIDDEN_IMPORTS:
                issues.append(f"forbidden_import_from: {node.module}")

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                issues.append(f"forbidden_call: {node.func.id}")

    for pattern in RISKY_TEXT_PATTERNS:
        if re.search(pattern, module_code, flags=re.IGNORECASE):
            issues.append(f"risky_text_pattern: {pattern}")

    return len(issues) == 0, issues


def validate_skill_markdown(skill_md: str) -> tuple[bool, list[str]]:
    """
    Minimal SKILL.md frontmatter validation.
    """
    issues: list[str] = []

    if not skill_md.strip().startswith("---"):
        issues.append("missing_frontmatter_start")

    first_chunk = skill_md[:2000]
    if "name:" not in first_chunk:
        issues.append("missing_name_frontmatter")
    if "description:" not in first_chunk:
        issues.append("missing_description_frontmatter")

    if len(skill_md.encode("utf-8")) > 10_000_000:
        issues.append("skill_md_too_large")

    return len(issues) == 0, issues


def validate_harness_mutation(mutation: HarnessMutation) -> tuple[bool, list[str]]:
    """
    Minimal mutation validation.
    """
    issues: list[str] = []

    if not mutation.content.strip():
        issues.append("empty_content")

    if len(mutation.content) > 200_000:
        issues.append("content_too_large")

    return len(issues) == 0, issues


# =============================================================================
# AGENT-FACING TOOLS
# =============================================================================
#
# These tools expose the operational affordance layer discussed in the paper.
#
# The runtime intentionally avoids hardcoding cognition procedurally.
#
# Instead, it exposes:
#     - persistence
#     - trace inspection
#     - validation primitives
#     - mutation proposals
#     - lifecycle transitions
#
# The agent loop itself performs:
#     - interpretation
#     - synthesis
#     - reflection
#     - governance reasoning
#     - capability abstraction

# =============================================================================

@tool
def record_execution_trace(
        event_type: str,
        summary: str,
        success: bool | None = None,
        latency_ms: float | None = None,
        payload_json: str = "{}",
) -> str:
    """
    Record an execution trace event for later harness evolution.

    The agent should call this when it observes reusable behavior, recurring
    failures, missing validators, brittle transformations, or useful outcomes.
    """
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        payload = {"raw_payload": payload_json}

    event = TraceEvent(
        event_type=event_type,
        summary=summary,
        success=success,
        latency_ms=latency_ms,
        payload=payload,
    )

    append_jsonl(TRACE_FILE, event.model_dump())

    return json.dumps(
        {
            "status": "recorded",
            "event_id": event.event_id,
            "trace_file": str(TRACE_FILE),
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
def inspect_recent_traces(limit: int = 20) -> str:
    """
    Inspect recent execution traces.

    No Python pattern detector is used. The LLM must infer whether there is a
    reusable operational pattern.
    """
    return json.dumps(load_recent_traces(limit=limit), indent=2, ensure_ascii=False)


@tool
def write_generated_skill(
        skill_name: str,
        description: str,
        skill_md: str,
        module_py: str,
        tests_py: str = "",
        metadata_json: str = "{}",
) -> str:
    """
    Create a DeepAgents-compatible generated skill.

    IMPORTANT:
        The LLM writes all content. The kernel only validates and persists.

    Files:
        - SKILL.md
        - module.py
        - metadata.json
        - tests/test_module.py, optional
    """
    skill_slug = safe_slug(skill_name)
    skill_id = f"{skill_slug}_{uuid.uuid4().hex[:8]}"
    skill_dir = GENERATED_SKILLS_DIR / skill_id
    tests_dir = skill_dir / "tests"

    md_ok, md_issues = validate_skill_markdown(skill_md)
    py_ok, py_issues = validate_python_module(module_py)

    if tests_py.strip():
        test_ok, test_issues = validate_python_module(tests_py)
    else:
        test_ok, test_issues = True, []

    if not md_ok or not py_ok or not test_ok:
        return json.dumps(
            {
                "status": "rejected",
                "reason": "validation_failed",
                "skill_md_issues": md_issues,
                "module_py_issues": py_issues,
                "tests_py_issues": test_issues,
            },
            indent=2,
            ensure_ascii=False,
        )

    try:
        metadata = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        metadata = {"raw_metadata": metadata_json}

    metadata.update(
        {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "description": description,
            "created_at": utc_now_iso(),
            "stage": "experimental",
            "generated_by": "LLM via write_generated_skill",
        }
    )

    skill_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(skill_md.strip() + "\n", encoding="utf-8")
    (skill_dir / "module.py").write_text(module_py.strip() + "\n", encoding="utf-8")
    (skill_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    files = ["SKILL.md", "module.py", "metadata.json"]

    if tests_py.strip():
        (tests_dir / "test_module.py").write_text(tests_py.strip() + "\n", encoding="utf-8")
        files.append("tests/test_module.py")

    spec = GeneratedSkillSpec(
        skill_id=skill_id,
        name=skill_name,
        description=description,
        skill_dir=str(skill_dir),
        files=files,
        metadata=metadata,
    )

    upsert_skill_registry(spec)

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="generated_skill_created",
            summary=f"Generated skill {skill_id}: {description}",
            success=True,
            related_artifacts=[skill_id],
            payload={
                "skill_dir": str(skill_dir),
                "files": files,
            },
        ).model_dump(),
    )

    return json.dumps(
        {
            "status": "created",
            "skill_id": skill_id,
            "skill_dir": str(skill_dir),
            "files": files,
            "stage": "experimental",
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
# Implements: capability validation and lifecycle transition gates.
def validate_generated_skill(skill_id: str) -> str:
    """
    Validate a generated skill using kernel-level static checks.

    In production, connect this to:
        - sandbox backend
        - pytest
        - CI
        - Langfuse evals
        - security scan
    """
    specs = load_skill_registry()
    matches = [item for item in specs if item.skill_id == skill_id]

    if not matches:
        return json.dumps({"status": "not_found", "skill_id": skill_id}, indent=2)

    spec = matches[0]
    skill_dir = Path(spec.skill_dir)

    issues: list[str] = []

    skill_md_path = skill_dir / "SKILL.md"
    module_path = skill_dir / "module.py"
    tests_path = skill_dir / "tests" / "test_module.py"

    if not skill_md_path.exists():
        issues.append("missing_SKILL.md")
    else:
        md_ok, md_issues = validate_skill_markdown(skill_md_path.read_text(encoding="utf-8"))
        if not md_ok:
            issues.extend(md_issues)

    if not module_path.exists():
        issues.append("missing_module.py")
    else:
        py_ok, py_issues = validate_python_module(module_path.read_text(encoding="utf-8"))
        if not py_ok:
            issues.extend(py_issues)

    if tests_path.exists():
        test_ok, test_issues = validate_python_module(tests_path.read_text(encoding="utf-8"))
        if not test_ok:
            issues.extend(test_issues)
    else:
        issues.append("missing_tests_recommended")

    # Missing tests are advisory: still allow "validated" if no blocking issues.
    blocking_issues = [x for x in issues if x != "missing_tests_recommended"]

    if blocking_issues:
        status = "failed"
        spec.stage = "experimental"
    else:
        status = "validated"
        spec.stage = "validated"

    spec.metadata["last_validation"] = {
        "timestamp": utc_now_iso(),
        "status": status,
        "issues": issues,
    }

    upsert_skill_registry(spec)

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="generated_skill_validation",
            summary=f"Validation for {skill_id}: {status}",
            success=(status == "validated"),
            related_artifacts=[skill_id],
            payload={"issues": issues},
        ).model_dump(),
    )

    return json.dumps(
        {
            "status": status,
            "skill_id": skill_id,
            "issues": issues,
            "stage": spec.stage,
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
def record_capability_review(
        artifact_id: str,
        reviewer: str,
        verdict: Literal["accept", "revise", "reject", "promote", "deprecate"],
        rationale: str,
        evidence_json: str = "{}",
) -> str:
    """
    Record an agent-authored review of a skill, mutation, workflow, or evaluator.

    This supports multi-agent review over shared code artifacts.
    """
    try:
        evidence = json.loads(evidence_json or "{}")
    except json.JSONDecodeError:
        evidence = {"raw_evidence": evidence_json}

    review = CapabilityReview(
        artifact_id=artifact_id,
        reviewer=reviewer,
        verdict=verdict,
        rationale=rationale,
        evidence=evidence,
    )

    append_review(review)

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="capability_review_recorded",
            summary=f"{reviewer} reviewed {artifact_id}: {verdict}",
            success=True,
            related_artifacts=[artifact_id, review.review_id],
            payload=review.model_dump(),
        ).model_dump(),
    )

    return review.model_dump_json(indent=2)


@tool
def promote_skill_stage(
        skill_id: str,
        new_stage: Literal["experimental", "validated", "trusted", "canonical", "deprecated"],
        rationale: str,
) -> str:
    """
    Promote or demote generated skill.

    Canonical promotion requires the skill to be validated or trusted.
    """
    specs = load_skill_registry()
    matches = [item for item in specs if item.skill_id == skill_id]

    if not matches:
        return json.dumps({"status": "not_found", "skill_id": skill_id}, indent=2)

    spec = matches[0]

    if new_stage == "canonical" and spec.stage not in {"validated", "trusted", "canonical"}:
        return json.dumps(
            {
                "status": "rejected",
                "reason": "canonical_requires_prior_validation",
                "current_stage": spec.stage,
            },
            indent=2,
            ensure_ascii=False,
        )

    spec.stage = new_stage
    spec.metadata["last_stage_change"] = {
        "timestamp": utc_now_iso(),
        "new_stage": new_stage,
        "rationale": rationale,
    }

    upsert_skill_registry(spec)

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="skill_stage_change",
            summary=f"{skill_id} -> {new_stage}",
            success=True,
            related_artifacts=[skill_id],
            payload={"rationale": rationale},
        ).model_dump(),
    )

    return json.dumps(
        {
            "status": "updated",
            "skill_id": skill_id,
            "new_stage": new_stage,
            "rationale": rationale,
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
def list_generated_skills() -> str:
    """
    List generated skills and lifecycle stages.
    """
    return json.dumps([item.model_dump() for item in load_skill_registry()], indent=2, ensure_ascii=False)


@tool
# Implements: governed mutation proposal stage from the paper.
def propose_harness_mutation(
        target_type: Literal["system_prompt", "policy", "workflow", "routing_rule", "evaluation_contract"],
        target_name: str,
        rationale: str,
        content: str,
        risk_level: Literal["low", "medium", "high"] = "medium",
) -> str:
    """
    Propose a governed self-modification of the harness.

    The mutation is stored as candidate first. It is not active until promoted.
    """
    mutation = HarnessMutation(
        target_type=target_type,
        target_name=safe_slug(target_name),
        rationale=rationale,
        content=content,
        risk_level=risk_level,
    )

    valid, issues = validate_harness_mutation(mutation)
    if not valid:
        return json.dumps(
            {
                "status": "rejected",
                "issues": issues,
                "mutation": mutation.model_dump(),
            },
            indent=2,
            ensure_ascii=False,
        )

    upsert_mutation(mutation)

    candidate_path = MUTATIONS_DIR / f"{mutation.mutation_id}_{mutation.target_name}.md"
    candidate_path.write_text(
        textwrap.dedent(
            f"""
            # Harness Mutation Candidate

            mutation_id: {mutation.mutation_id}
            target_type: {mutation.target_type}
            target_name: {mutation.target_name}
            risk_level: {mutation.risk_level}
            stage: {mutation.stage}
            timestamp: {mutation.timestamp}

            ## Rationale

            {mutation.rationale}

            ## Proposed Content

            {mutation.content}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
        )

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="harness_mutation_proposed",
            summary=f"Proposed {target_type} mutation: {target_name}",
            success=True,
            related_artifacts=[mutation.mutation_id],
            payload={
                "candidate_path": str(candidate_path),
                "risk_level": risk_level,
            },
        ).model_dump(),
    )

    return json.dumps(
        {
            "status": "proposed",
            "mutation_id": mutation.mutation_id,
            "candidate_path": str(candidate_path),
            "risk_level": risk_level,
            "note": "Mutation is not active until promoted.",
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
# Implements: governed mutation promotion and bounded runtime evolution.
def promote_harness_mutation(mutation_id: str, approval_note: str = "") -> str:
    """
    Promote a harness mutation into active harness files.

    High-risk mutations require approval_note. In production this should be
    connected to HITL middleware or an external approval service.
    """
    mutations = load_mutations()
    matches = [item for item in mutations if item.mutation_id == mutation_id]

    if not matches:
        return json.dumps({"status": "not_found", "mutation_id": mutation_id}, indent=2)

    mutation = matches[0]

    if mutation.risk_level == "high" and not approval_note.strip():
        return json.dumps(
            {
                "status": "blocked",
                "reason": "high_risk_mutation_requires_approval_note",
                "mutation_id": mutation_id,
            },
            indent=2,
            ensure_ascii=False,
        )

    if mutation.target_type == "system_prompt":
        target_path = PROMPTS_DIR / f"{mutation.target_name}.md"
    elif mutation.target_type == "policy":
        target_path = POLICIES_DIR / f"{mutation.target_name}.md"
    elif mutation.target_type == "workflow":
        target_path = WORKFLOWS_DIR / f"{mutation.target_name}.md"
    elif mutation.target_type == "routing_rule":
        target_path = ROUTING_RULES_DIR / f"{mutation.target_name}.md"
    else:
        target_path = EVALUATION_CONTRACTS_DIR / f"{mutation.target_name}.md"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(mutation.content.strip() + "\n", encoding="utf-8")

    mutation.stage = "promoted"
    upsert_mutation(mutation)

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="harness_mutation_promoted",
            summary=f"Promoted mutation {mutation_id} to {target_path}",
            success=True,
            related_artifacts=[mutation_id],
            payload={
                "target_path": str(target_path),
                "approval_note": approval_note,
            },
        ).model_dump(),
    )

    return json.dumps(
        {
            "status": "promoted",
            "mutation_id": mutation_id,
            "target_path": str(target_path),
            "approval_note": approval_note,
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
def inspect_harness_state(include_recent_traces: bool = True) -> str:
    """
    Inspect current harness state.

    This is the agent's introspection surface.
    """
    state = HarnessState(
        generated_skills=load_skill_registry(),
        mutations=load_mutations(),
        recent_traces=load_recent_traces(limit=25) if include_recent_traces else [],
        active_system_prompt_files=[str(p) for p in sorted(PROMPTS_DIR.glob("*.md"))],
        active_policy_files=[str(p) for p in sorted(POLICIES_DIR.glob("*.md"))],
        active_workflow_files=[str(p) for p in sorted(WORKFLOWS_DIR.glob("*.md"))],
        active_routing_rule_files=[str(p) for p in sorted(ROUTING_RULES_DIR.glob("*.md"))],
        active_evaluation_contract_files=[str(p) for p in sorted(EVALUATION_CONTRACTS_DIR.glob("*.md"))],
    )
    return state.model_dump_json(indent=2)


@tool
def read_harness_file(relative_path: str) -> str:
    """
    Read a harness file under runtime_v10.

    Example:
        harness/prompts/system_prompt.md
    """
    candidate = (RUNTIME_DIR / relative_path).resolve()

    if not str(candidate).startswith(str(RUNTIME_DIR.resolve())):
        return json.dumps({"status": "blocked", "reason": "path_escape_attempt"}, indent=2)

    if not candidate.exists():
        return json.dumps({"status": "not_found", "path": str(candidate)}, indent=2)

    return candidate.read_text(encoding="utf-8")


@tool
def runtime_memory_note(
        title: str,
        content: str,
        runtime: ToolRuntime | None = None,
) -> str:
    """
    Record a note in runtime memory.

    With a full ToolRuntime store, this should be extended to write into
    runtime.store. Locally it writes to a file-backed memory note.
    """
    note_id = f"note_{safe_slug(title)}_{uuid.uuid4().hex[:8]}"
    note_path = RUNTIME_DIR / "memory_notes" / f"{note_id}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        textwrap.dedent(
            f"""
            # {title}

            created_at: {utc_now_iso()}

            {content}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
        )

    append_jsonl(
        TRACE_FILE,
        TraceEvent(
            event_type="runtime_memory_note",
            summary=f"Runtime memory note: {title}",
            success=True,
            related_artifacts=[note_id],
            payload={"note_path": str(note_path)},
        ).model_dump(),
    )

    return json.dumps({"status": "recorded", "note_id": note_id, "path": str(note_path)}, indent=2)


# =============================================================================
# DEEPAGENTS BACKEND AND MIDDLEWARE
# =============================================================================

def build_backend():
    """
    Build DeepAgents backend.

    Store routes represent the persistent substrate:
        - /memory/
        - /skills/
        - /harness/
        - /evals/
        - /telemetry/

    In production, namespaces should include assistant/org/user identifiers.
    """
    if not DEEPAGENTS_AVAILABLE:
        return None

    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/memory/": StoreBackend(namespace=lambda rt: ("governed_runtime_v10", "memory")),
            "/skills/": StoreBackend(namespace=lambda rt: ("governed_runtime_v10", "skills")),
            "/harness/": StoreBackend(namespace=lambda rt: ("governed_runtime_v10", "harness")),
            "/evals/": StoreBackend(namespace=lambda rt: ("governed_runtime_v10", "evals")),
            "/telemetry/": StoreBackend(namespace=lambda rt: ("governed_runtime_v10", "telemetry")),
        },
    )


def build_middleware(backend: Any) -> list[Any]:
    """
    Build middleware stack.

    V10 keeps strong operational limits to avoid runaway self-evolution.
    """
    middleware: list[Any] = []

    if LANGCHAIN_MIDDLEWARE_AVAILABLE:
        if TodoListMiddleware is not None:
            middleware.append(TodoListMiddleware())

        if ModelCallLimitMiddleware is not None:
            middleware.append(ModelCallLimitMiddleware(run_limit=50, thread_limit=150, exit_behavior="end"))

        if ToolCallLimitMiddleware is not None:
            middleware.append(ToolCallLimitMiddleware(run_limit=100, thread_limit=300))

        if ToolRetryMiddleware is not None:
            middleware.append(ToolRetryMiddleware(max_retries=2))

        if ModelRetryMiddleware is not None:
            middleware.append(ModelRetryMiddleware(max_retries=2))

        if SummarizationMiddleware is not None:
            middleware.append(
                SummarizationMiddleware(
                    model=os.getenv("DEEPAGENTS_SUMMARY_MODEL", "openai:gpt-5.4-mini"),
                    trigger=("messages", 30),
                    keep=("messages", 12),
                )
            )

    if QUICKJS_AVAILABLE and CodeInterpreterMiddleware is not None:
        try:
            middleware.append(
                CodeInterpreterMiddleware(
                    skills_backend=backend,
                    max_ptc_calls=160,
                    ptc=["task"],
                )
            )
        except TypeError:
            middleware.append(CodeInterpreterMiddleware())

    return middleware


# =============================================================================
# SUBAGENTS
# =============================================================================
#
# Runtime evolution is framed as a multi-agent governance process.
#
# Specialized operational roles:
#
#     runtime-evolution-agent
#         -> capability generation
#
#     skill-validator-agent
#         -> validation and review
#
#     harness-governor-agent
#         -> mutation governance
#
#     task-worker-agent
#         -> operational execution
#
#     reflection-agent
#         -> strategic introspection
#
# This decomposition operationalizes the paper's governance-oriented runtime
# evolution model.

# =============================================================================

# Implements: multi-agent governance specialization model from the paper.
def build_subagents() -> list[dict[str, Any]]:
    """
    V10 subagents.

    The runtime evolution logic is delegated to specialized agents rather than embedded directly in the Python kernel.
    """

    runtime_evolution_agent = {
        "name": "runtime-evolution-agent",
        "description": (
            "Inspects traces and harness state, detects reusable operational "
            "patterns, creates DeepAgents skills, records reviews, and proposes "
            "self-modifications of prompts, policies, workflows, routing rules, "
            "or evaluation contracts."
        ),
        "system_prompt": textwrap.dedent(
            """
            You are the Runtime Evolution Agent.

            You own the cognitive evolution loop.

            You must:
            1. Inspect recent traces and harness state.
            2. Infer whether there is a reusable operational pattern.
            3. Reuse existing skills when sufficient.
            4. Create a new skill only when useful.
            5. If creating a skill, author SKILL.md, module.py, tests, and metadata.
            6. Validate the generated skill.
            7. Record a capability review.
            8. Propose prompt, policy, workflow, routing, or evaluation mutations
               only when the harness itself is a bottleneck.

            Rules:
            - Do not rely on hardcoded templates.
            - Generated code is operational memory.
            - Keep skills small, composable, testable.
            - Never promote high-risk harness changes without approval.
            - Prefer governed additive evolution over destructive rewriting.
            """
        ).strip(),
        "tools": [
            inspect_recent_traces,
            inspect_harness_state,
            list_generated_skills,
            write_generated_skill,
            validate_generated_skill,
            record_capability_review,
            promote_skill_stage,
            propose_harness_mutation,
            promote_harness_mutation,
            read_harness_file,
            runtime_memory_note,
        ],
        "skills": ["/skills/generated/", "/skills/canonical/"],
    }

    skill_validator_agent = {
        "name": "skill-validator-agent",
        "description": (
            "Reviews generated skills for correctness, safety, minimality, tests, "
            "metadata quality, reuse value and promotion readiness."
        ),
        "system_prompt": textwrap.dedent(
            """
            You are the Skill Validator Agent.

            Validate generated skills against:
            - correctness
            - safety
            - minimality
            - reusability
            - testability
            - alignment with runtime policies
            - quality of metadata and examples

            Use validation tools, inspect policies, and record a review artifact.
            """
        ).strip(),
        "tools": [
            validate_generated_skill,
            list_generated_skills,
            inspect_harness_state,
            read_harness_file,
            record_capability_review,
            promote_skill_stage,
        ],
        "skills": ["/skills/generated/", "/skills/canonical/"],
    }

    harness_governor_agent = {
        "name": "harness-governor-agent",
        "description": (
            "Reviews harness mutations, policies, routing rules, evaluation "
            "contracts, approval boundaries and risk controls."
        ),
        "system_prompt": textwrap.dedent(
            """
            You are the Harness Governor Agent.

            Your role is to prevent uncontrolled self-modification.

            Review:
            - prompt changes
            - policy changes
            - workflow changes
            - routing rules
            - evaluation contracts

            Separate:
            - low-risk additive improvements
            - medium-risk behavioral changes
            - high-risk permission/security/deployment changes

            High-risk changes must remain proposed unless explicit approval exists.
            """
        ).strip(),
        "tools": [
            inspect_harness_state,
            read_harness_file,
            propose_harness_mutation,
            promote_harness_mutation,
            record_capability_review,
        ],
        "skills": ["/skills/canonical/"],
    }

    task_worker_agent = {
        "name": "task-worker-agent",
        "description": (
            "Executes ordinary work, reuses skills, records traces, and flags "
            "repeated behavior for runtime evolution."
        ),
        "system_prompt": textwrap.dedent(
            """
            You are the Task Worker Agent.

            Solve delegated tasks using available skills.

            Record traces when you observe:
            - repeated manual steps
            - brittle transformations
            - missing validators
            - recurring failures
            - reusable workflows
            - capability gaps
            """
        ).strip(),
        "tools": [
            record_execution_trace,
            inspect_harness_state,
            list_generated_skills,
            runtime_memory_note,
        ],
        "skills": ["/skills/generated/", "/skills/canonical/"],
    }

    reflection_agent = {
        "name": "reflection-agent",
        "description": (
            "Analyzes failures, loops, poor evaluations, weak capabilities and "
            "proposes strategic improvements."
        ),
        "system_prompt": textwrap.dedent(
            """
            You are the Reflection Agent.

            Identify:
            - repeated failures
            - weak verification
            - costly loops
            - missing policies
            - low-quality skills
            - poor routing decisions

            Then propose concrete next actions:
            - reuse existing capability
            - create a new skill
            - improve a workflow
            - add an evaluation contract
            - ask for human approval
            """
        ).strip(),
        "tools": [
            inspect_recent_traces,
            inspect_harness_state,
            list_generated_skills,
            propose_harness_mutation,
            runtime_memory_note,
        ],
        "skills": ["/skills/generated/", "/skills/canonical/"],
    }

    return [
        runtime_evolution_agent,
        skill_validator_agent,
        harness_governor_agent,
        task_worker_agent,
        reflection_agent,
    ]


# =============================================================================
# SYSTEM PROMPT COMPOSITION
# =============================================================================
#
# Prompts, workflows, routing rules and evaluators are treated as governed
# runtime artifacts rather than static configuration.
#
# Promoted mutations become part of future runtime cognition, enabling
# persistent but bounded runtime evolution.

# =============================================================================

# Implements: persistent operational substrate composition
# described in the runtime governance sections of the paper.
def compose_system_prompt() -> str:
    """
    Compose system prompt from active harness specs.

    This is what makes self-modifying harness specs actually influence future
    behavior after promotion.
    """
    prompt_sections: list[str] = []

    for directory in [
        PROMPTS_DIR,
        POLICIES_DIR,
        WORKFLOWS_DIR,
        ROUTING_RULES_DIR,
        EVALUATION_CONTRACTS_DIR,
    ]:
        for file in sorted(directory.glob("*.md")):
            prompt_sections.append(file.read_text(encoding="utf-8"))

    prompt_sections.append(
        textwrap.dedent(
            """
            # V10 Kernel Rule

            The runtime kernel exposes governed affordances.

            The agent owns:
            - pattern detection
            - capability abstraction
            - skill writing
            - evaluator design
            - mutation proposals
            - reuse decisions
            - promotion rationale

            The kernel owns:
            - persistence
            - basic validation
            - audit trail
            - lifecycle state
            - risk gates
            - filesystem boundaries

            This separation is intentional:
            Python is the kernel, not the intelligence.
            Code artifacts are the persistent operational substrate.
            """
        ).strip()
    )

    return "\n\n---\n\n".join(prompt_sections)


# =============================================================================
# AGENT FACTORY
# =============================================================================
#
# This section binds the governance substrate to LangGraph DeepAgents.
#
# DeepAgents provides orchestration.
#
# This runtime layers:
#     - lifecycle governance
#     - persistent capability evolution
#     - operational memory
#     - runtime mutation control
#
# on top of the existing runtime infrastructure.

# =============================================================================

def build_agent():
    """
    Build the DeepAgents runtime.
    """
    if not DEEPAGENTS_AVAILABLE:
        logger.warning("DeepAgents is not installed. Returning None.")
        return None

    backend = build_backend()
    middleware = build_middleware(backend)
    checkpointer = MemorySaver() if MemorySaver is not None else None
    store = InMemoryStore() if InMemoryStore is not None else None

    model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-5.4")

    agent = create_deep_agent(
        model=model,
        name="governed-agent-runtime",
        system_prompt=compose_system_prompt(),
        tools=[
            record_execution_trace,
            inspect_recent_traces,
            write_generated_skill,
            validate_generated_skill,
            record_capability_review,
            promote_skill_stage,
            list_generated_skills,
            propose_harness_mutation,
            promote_harness_mutation,
            inspect_harness_state,
            read_harness_file,
            runtime_memory_note,
        ],
        subagents=build_subagents(),
        backend=backend,
        store=store,
        memory=[
            "/memory/AGENTS.md",
            "/harness/prompts/system_prompt.md",
            "/harness/policies/runtime_policy.md",
            "/harness/workflows/runtime_evolution_workflow.md",
            "/harness/routing_rules/runtime_routing.md",
            "/harness/evaluation_contracts/skill_evaluation_contract.md",
        ],
        skills=[
            "/skills/generated/",
            "/skills/canonical/",
        ],
        middleware=middleware,
        checkpointer=checkpointer,
        debug=True,
    )

    return agent


# =============================================================================
# INITIAL FILES FOR STATEBACKEND SEEDING
# =============================================================================

def build_initial_files() -> dict[str, Any]:
    """
    Seed DeepAgents virtual filesystem.

    StateBackend requires files to be injected per invocation. StoreBackend routes
    can persist equivalent paths in deployment.
    """
    if create_file_data is None:
        return {}

    files: dict[str, Any] = {}

    files["/memory/AGENTS.md"] = create_file_data(
        textwrap.dedent(
            """
            # Agent Memory

            Generated code artifacts are operational memory.

            Convert validated recurring behavior into:
            - skills
            - tests
            - evaluators
            - policies
            - workflows
            - routing rules
            - regression contracts
            """
        ).strip()
        + "\n"
    )

    for directory, virtual_prefix in [
        (PROMPTS_DIR, "/harness/prompts/"),
        (POLICIES_DIR, "/harness/policies/"),
        (WORKFLOWS_DIR, "/harness/workflows/"),
        (ROUTING_RULES_DIR, "/harness/routing_rules/"),
        (EVALUATION_CONTRACTS_DIR, "/harness/evaluation_contracts/"),
    ]:
        for file in sorted(directory.glob("*.md")):
            files[f"{virtual_prefix}{file.name}"] = create_file_data(file.read_text(encoding="utf-8"))

    for skill_dir in sorted(GENERATED_SKILLS_DIR.glob("*")):
        if not skill_dir.is_dir():
            continue
        for file in skill_dir.rglob("*"):
            if file.is_file():
                virtual_path = "/skills/generated/" + str(file.relative_to(GENERATED_SKILLS_DIR)).replace(os.sep, "/")
                files[virtual_path] = create_file_data(file.read_text(encoding="utf-8"))

    for skill_dir in sorted(CANONICAL_SKILLS_DIR.glob("*")):
        if not skill_dir.is_dir():
            continue
        for file in skill_dir.rglob("*"):
            if file.is_file():
                virtual_path = "/skills/canonical/" + str(file.relative_to(CANONICAL_SKILLS_DIR)).replace(os.sep, "/")
                files[virtual_path] = create_file_data(file.read_text(encoding="utf-8"))

    return files



# -----------------------------------------------------------------------------
# Runtime Evolution Loop
# -----------------------------------------------------------------------------
#
# The runtime operationalizes the lifecycle proposed in the paper:
#
#     generate
#         -> execute
#             -> evaluate
#                 -> persist
#                     -> mutate
#                         -> govern
#                             -> promote
#
# Governance determines whether generated operational behavior becomes part of
# the persistent runtime substrate.
#

# =============================================================================
# DEMO TASK AND TRACE SEEDING
# =============================================================================

DEMO_TASK = """
We are testing the Governed Runtime Evolution runtime.

Objectives:
1. Inspect recent traces.
2. Decide whether there is a reusable operational pattern.
3. If yes, delegate to runtime-evolution-agent.
4. The runtime-evolution-agent should generate a real DeepAgents skill using
   write_generated_skill. The skill content must be authored by the agent.
5. Validate the generated skill.
6. Record a capability review.
7. If the harness itself needs improvement, propose a governed harness mutation.
8. Explain which artifacts were generated and why.

Important:
- Do not rely on hardcoded payload normalizer behavior.
- The agent must infer the capability from traces.
- Treat generated code as operational memory.
- Keep risky mutations proposed, not promoted.
"""


async def seed_demo_traces() -> None:
    """
    Seed traces only as observations.

    There is no Python pattern detector here. The agent must inspect these traces
    and decide what to do.
    """
    demo_events = [
        TraceEvent(
            event_type="manual_csv_schema_validation",
            summary="Repeatedly validated CSV columns against expected schema before analysis.",
            success=True,
            latency_ms=12,
            payload={
                "columns": ["id", "timestamp", "value"],
                "expected": ["id", "timestamp", "value"],
                "candidate_reusable_capability": True,
            },
        ),
        TraceEvent(
            event_type="manual_csv_schema_validation",
            summary="Validated another CSV schema and normalized column names.",
            success=True,
            latency_ms=15,
            payload={
                "normalization": "lowercase_strip",
                "candidate_reusable_capability": True,
            },
        ),
        TraceEvent(
            event_type="manual_csv_schema_validation",
            summary="Detected missing required CSV column and produced diagnostic.",
            success=True,
            latency_ms=18,
            payload={
                "missing_column": "timestamp",
                "candidate_reusable_capability": True,
            },
        ),
    ]

    for event in demo_events:
        append_jsonl(TRACE_FILE, event.model_dump())


# =============================================================================
# MAIN
# =============================================================================

async def main() -> None:
    """
    Example invocation.

    The evolutionary decision is delegated to the DeepAgent loop. Python only
    exposes governed affordances.
    """
    logger.info("=" * 96)
    logger.info("GOVERNED RUNTIME EVOLUTION — GOVERNED SELF-EVOLVING COGNITIVE RUNTIME")
    logger.info("=" * 96)

    await seed_demo_traces()

    agent = build_agent()

    if agent is None:
        logger.warning(
            "DeepAgents is not available. Runtime files and tools were created, "
            "but the agent cannot be invoked in this environment."
        )
        logger.info("Runtime directory: %s", RUNTIME_DIR)
        return

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": DEMO_TASK,
                }
            ],
            "files": build_initial_files(),
        },
        config={
            "configurable": {
                "thread_id": "code-as-agent-harness-demo",
                "assistant_id": "governed-agent-runtime",
            },
            "metadata": {
                "assistant_id": "governed-agent-runtime",
                "user_id": "default-user",
                "org_id": "default-org",
            },
        },
        context=RuntimeContext(),
    )

    logger.info("=" * 96)
    logger.info("FINAL OUTPUT")
    logger.info("=" * 96)

    try:
        print(result["messages"][-1].content)
    except Exception:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
