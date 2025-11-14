from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class ProjectCreate(BaseModel):
    id: str
    name: str
    task_type: str = "code"  # code, research, writing, data_analysis, document_processing
    domain_config: dict[str, Any] | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    task_type: str
    domain_config: dict[str, Any] | None
    created_at: str


class RunCreate(BaseModel):
    project_id: str
    name: str
    instructions: str
    reference_run_id: str | None = None
    from_run_id: str | None = Field(default=None, description="Optional run to clone workspace from")


class RunRead(BaseModel):
    id: str
    project_id: str
    name: str
    created_at: str
    status: str
    reference_run_id: str | None = None
    workspace_from_run_id: str | None = None
    system_instructions: str | None = None
    codex_thread_id: str | None = None


class StepRead(BaseModel):
    id: str
    run_id: str
    t: str
    role: str
    content: str
    intent_kind: str | None = None
    intent_target: str | None = None
    outcome_ok: bool | None = None
    files_json: str | None = None
    tool_name: str | None = None
    tool_args_json: str | None = None
    outcome_notes_json: str | None = None


class ArtifactRead(BaseModel):
    id: str
    run_id: str
    kind: str
    path: str
    bytes: int
    created_at: str


class PatternRead(BaseModel):
    id: str
    source_run_id: str
    name: str
    summary: str
    steps: list[dict[str, Any]]
    variables: dict[str, Any]
