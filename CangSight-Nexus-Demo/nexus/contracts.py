"""Strict records and content identities shared by the control plane."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('schema_version',mode='before',check_fields=False)
    @classmethod
    def integer_schema_version(cls,value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer')
        return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def source_manifest(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if rel.parts[0] in ('target', '.git'):
            continue
        if path.is_symlink():
            raise ValueError('symlinks are forbidden')
        if path.is_file():
            result[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def tree_hash(root: Path) -> str:
    return digest(source_manifest(root))


def editable_path(value: str) -> str:
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value or p.as_posix() != value:
        raise ValueError('invalid relative path')
    if not value.startswith('src/') or p.suffix != '.cj' or p.name.endswith('_test.cj'):
        raise ValueError('only existing production .cj sources may be edited')
    return value


class Edit(Record):
    path: str
    before_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    content: str = Field(max_length=131072)
    _path = field_validator('path')(editable_path)


class CandidateProposal(Record):
    edits: list[Edit] = Field(min_length=1, max_length=3)
    requirement_refs: list[str] = Field(min_length=1)

    @field_validator('edits')
    @classmethod
    def unique_paths(cls, edits):
        if len({e.path for e in edits}) != len(edits):
            raise ValueError('duplicate edit paths')
        return edits


State = Literal['PASS', 'FAIL', 'UNKNOWN', 'NOT_RUN']
TaskState = Literal['READY', 'DIAGNOSING', 'GENERATING', 'APPLYING', 'BUILDING', 'TESTING',
                    'REVIEW_PENDING', 'EXPORTING', 'DELIVERED', 'UNREPAIRED', 'BLOCKED',
                    'REJECTED', 'CANCELLED', 'IN_DOUBT']


class TaskRecord(Record):
    schema_version: Literal[1, 2] = 1
    revision: int = Field(default=0, ge=0)
    spec_id: str | None = None
    spec_hash: str | None = None
    verification_plan_id: str | None = None
    verification_plan_hash: str | None = None
    runtime_binding: dict = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    budget: dict = Field(default_factory=lambda: {'candidates':3,'seconds':480,'output_tokens':20000})
    id: str
    baseline_id: str
    goal: str
    allowed_paths: list[str]
    test_plan: dict = Field(default_factory=lambda: {'build': ['cjpm', 'build', '-V'], 'test': ['cjpm', 'test']})
    status: TaskState = 'READY'
    attempt_count: int = Field(default=0, ge=0, le=3)

    @model_validator(mode='after')
    def complete_v11_binding(self):
        if self.schema_version == 2 and not all((self.spec_id,self.spec_hash,self.verification_plan_id,self.verification_plan_hash)):
            raise ValueError('V1.1 tasks require a complete requirement and verification plan binding')
        return self


class CandidateRecord(Record):
    schema_version: Literal[1, 2] = 1
    spec_hash: str | None = None
    verification_plan_hash: str | None = None
    model_call_id: str | None = None
    id: str
    task_id: str
    baseline_hash: str
    edits: list[Edit]
    tree_hash: str
    diff_ref: str
    attempt: int = Field(ge=1, le=3)


class ToolResult(Record):
    schema_version: Literal[1] = 1
    operation_status: Literal['OK', 'ERROR', 'IN_DOUBT']
    data: dict = Field(default_factory=dict)
    error: str | None = None
    record_refs: list[str] = Field(default_factory=list)


class CheckResult(Record):
    schema_version: Literal[1, 2] = 1
    argv: list[str] = Field(default_factory=list)
    execution_argv: list[list[str]] = Field(default_factory=list)
    working_root: str | None = None
    toolchain_hash: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    report_ref: str | None = None
    case_results: dict[str, State] = Field(default_factory=dict)
    suite_results: dict[str, dict] = Field(default_factory=dict)
    spec_hash: str | None = None
    verification_plan_hash: str | None = None
    limitations: list[str] = Field(default_factory=list)
    id: str = ''
    subject_id: str = ''
    plan_hash: str = ''
    tree_hash: str = ''
    kind: Literal['build', 'test'] = 'test'
    state: State
    exit_code: int | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    log_ref: str = ''
    diagnostics: str = ''


class AcceptanceRecord(Record):
    schema_version: Literal[1, 2] = 1
    task_id: str | None = None
    spec_hash: str | None = None
    verification_plan_hash: str | None = None
    actor_id: str | None = None
    allowed_action: Literal['candidate.export'] = 'candidate.export'
    review_id: str | None = None
    id: str
    candidate_id: str
    tree_hash: str
    check_set_hash: str
    expires_at: float
    export_id: str | None = None

    @model_validator(mode='after')
    def complete_approval(self):
        if self.schema_version==2 and not all((self.task_id,self.spec_hash,self.verification_plan_hash,self.actor_id,self.review_id)):
            raise ValueError('V1.1 acceptance requires identity, review and frozen requirement binding')
        return self


class ReviewRecord(Record):
    schema_version: Literal[1] = 1
    id: str
    task_id: str
    candidate_id: str
    spec_hash: str | None
    verification_plan_hash: str | None
    requirement_results: list[dict] = Field(default_factory=list)
    check_set_hash: str | None
    decision: Literal['ACCEPT','REJECT']
    decision_source: Literal['USER'] = 'USER'
    actor_id: str = Field(min_length=1,max_length=128)
    reason: str = Field(default='',max_length=2000)


class RunEvent(Record):
    schema_version: Literal[1] = 1
    event_id: str
    task_id: str
    sequence: int = Field(ge=1)
    type: str
    candidate_id: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    object_ref: str | None = None
    status: str
    occurred_at: float
    data: dict = Field(default_factory=dict)


class ModelCall(Record):
    schema_version: Literal[1] = 1
    id: str
    task_id: str
    origin: Literal['LIVE', 'TEST']
    model_id: str
    request_ref: str
    response_ref: str | None = None
    usage: dict = Field(default_factory=dict)
    status: Literal['STARTED', 'SUCCEEDED', 'FAILED', 'IN_DOUBT']


class ToolCall(Record):
    schema_version: Literal[1] = 1
    request_id: str | None = None
    tool_version: str | None = None
    input_tree_hash: str | None = None
    request_ref: str | None = None
    replayed: bool = False
    id: str
    task_id: str
    candidate_id: str | None = None
    tool: str
    status: str
    result_ref: str
    policy_ref: str | None = None


class RepairFeedback(Record):
    schema_version: Literal[1] = 1
    previous_candidate_id: str
    baseline_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    tree_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    diff: str
    edited_files: list[Edit] = Field(min_length=1, max_length=3)
    failed_checks: list[dict] = Field(min_length=1)
    diagnostic_snippets: list[dict] = Field(min_length=1)
    failure_cases: list[dict] = Field(default_factory=list, max_length=50)
    requirement_refs: list[str] = Field(min_length=1)
    remaining_budget: int = Field(ge=0, le=2)


class RequirementItem(Record):
    id: str = Field(pattern=r'^REQ-[A-Z][A-Z0-9-]*$')
    text: str = Field(min_length=1, max_length=2000)
    observable_behavior: str = Field(min_length=1, max_length=2000)
    preserves: list[str]
    uncovered: list[str]


class RequirementConfirmation(Record):
    schema_version: Literal[1]
    expected_version: int = Field(ge=1)
    requirements: list[RequirementItem] = Field(min_length=1, max_length=10)
    allowed_paths: list[str] = Field(min_length=1, max_length=3)

    @field_validator('requirements')
    @classmethod
    def unique_requirement_ids(cls, requirements):
        if len({r.id for r in requirements}) != len(requirements):
            raise ValueError('duplicate requirement IDs')
        return requirements

    @field_validator('allowed_paths')
    @classmethod
    def valid_allowed_paths(cls, paths):
        if len(set(paths)) != len(paths):
            raise ValueError('duplicate allowed paths')
        return [editable_path(p) for p in paths]


class RequirementSpec(Record):
    schema_version: Literal[1]
    id: str
    version: int = Field(ge=1)
    project_id: str
    source_text: str = Field(min_length=1, max_length=4000)
    requirements: list[RequirementItem]
    allowed_paths: list[str]
    confirmed_by: str = Field(min_length=1)
    spec_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


class VerificationPlan(Record):
    schema_version: Literal[1]
    id: str
    version: int = Field(ge=1)
    baseline_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    spec_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    toolchain_id: str = Field(min_length=1)
    required_suites: list[str]
    suite_tests: dict[str, list[str]]
    requirement_test_map: dict[str, list[str]]
    context_visibility: dict[str, Literal['PRODUCTION', 'PUBLIC_TEST', 'VERIFICATION_ONLY']]
    limitations: list[str]
    plan_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


class ToolRequest(Record):
    schema_version: Literal[1]
    tool_version: Literal['1.1']
    request_id: str = Field(min_length=1, max_length=128)
    input_tree_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    deadline_at: int = Field(ge=1)


class PolicyRequest(Record):
    schema_version: Literal[1]
    policy_version: Literal['1.1']
    action: str
    task_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    paths: list[str] = Field(max_length=3)
    input_tree_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    arguments_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    remaining_budget: int
    accepted: bool
    approval_binding: str = Field(pattern=r'^(?:|[a-f0-9]{64})$')
    deadline_at: int = Field(ge=1)


class PolicyResponse(Record):
    schema_version: Literal[1]
    policy_version: Literal['1.1']
    request_id: str
    input_tree_hash: str
    arguments_hash: str
    approval_binding: str
    decision: Literal['Allow', 'Deny', 'NeedApproval']
    reason: str
