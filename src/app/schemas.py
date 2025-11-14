from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class ProjectCreate(BaseModel):
    id: str
    name: str
    task_type: str = "code"  # code, research, writing, data_analysis, document_processing, document_writing, document_analysis
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
    task_type: str = Field(default="code", description="Task type for this run")
    reference_run_id: str | None = None
    from_run_id: str | None = Field(default=None, description="Optional run to clone workspace from")


class RunError(BaseModel):
    """Structured error information for DraftPunk integration."""
    step: str = Field(description="Step identifier where error occurred")
    tool: str = Field(description="Tool that caused the error")
    error_type: str = Field(description="Error classification: permission_error, runtime_error, tool_failure, etc.")
    message: str = Field(description="Human-readable error message")


class MachineSummary(BaseModel):
    """Machine-friendly run summary for LLM consumption."""
    goal: str = Field(description="Original task goal")
    primary_artifact: str | None = Field(description="Main output file path")
    secondary_artifacts: list[str] = Field(default_factory=list, description="Additional output files")
    execution_attempted: bool = Field(description="Whether execution was attempted")
    execution_succeeded: bool = Field(description="Whether execution completed successfully")
    reason_for_failure: str | None = Field(default=None, description="Why execution failed if applicable")
    notes: str | None = Field(default=None, description="Additional context about the run")


class RunRead(BaseModel):
    id: str
    project_id: str
    name: str
    created_at: str
    status: str
    task_type: str = Field(description="Task type: code, research, writing, etc.")
    progress: int = Field(ge=0, le=100, description="Progress percentage 0-100")
    had_errors: bool = Field(description="True if any hard failures occurred")
    errors: list[RunError] = Field(default_factory=list, description="Structured error records")
    artifacts: list["ArtifactRead"] = Field(default_factory=list, description="Generated artifacts")
    machine_summary: MachineSummary | None = Field(default=None, description="Structured summary for LLMs")
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


class WorkspaceFile(BaseModel):
    """File metadata in a run workspace."""
    path: str = Field(description="Workspace-relative file path")
    size_bytes: int = Field(description="File size in bytes")
    type: str = Field(description="File type guess: markdown, python, binary, etc.")


class WorkspaceFileListing(BaseModel):
    """Complete file listing for a run workspace."""
    run_id: str
    total_files: int
    files: list[WorkspaceFile]
