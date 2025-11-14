"""
DraftPunk Client Library

Minimal, typed client for DraftPunk to interact with Codex-Swarm backend.
Wraps HTTP API to provide clean Python interface.
"""

from __future__ import annotations

import httpx
from dataclasses import dataclass
from typing import Any, Literal


# Type aliases matching API
TaskType = Literal[
    "code",
    "research",
    "writing",
    "data_analysis",
    "document_processing",
    "document_writing",
    "document_analysis",
]

RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@dataclass
class RunError:
    """Structured error from a run."""

    step: str
    tool: str
    error_type: str
    message: str


@dataclass
class MachineSummary:
    """Machine-friendly run summary."""

    goal: str
    primary_artifact: str | None
    secondary_artifacts: list[str]
    execution_attempted: bool
    execution_succeeded: bool
    reason_for_failure: str | None = None
    notes: str | None = None


@dataclass
class Artifact:
    """File artifact from a run."""

    id: str
    run_id: str
    kind: str
    path: str
    bytes: int
    created_at: str


@dataclass
class RunSummary:
    """Complete run information."""

    run_id: str
    project_id: str
    task_type: TaskType
    status: RunStatus
    progress: int  # 0-100
    had_errors: bool
    errors: list[RunError]
    artifacts: list[Artifact]
    machine_summary: MachineSummary | None
    created_at: str


@dataclass
class WorkspaceFile:
    """File in run workspace."""

    path: str
    size_bytes: int
    type: str


@dataclass
class WorkspaceFileListing:
    """Complete workspace file listing."""

    run_id: str
    total_files: int
    files: list[WorkspaceFile]


class CodexSwarmClient:
    """
    Client for Codex-Swarm API.

    Usage:
        client = CodexSwarmClient(base_url="http://localhost:5050")
        run = client.start_run(
            project_id="my-project",
            instructions="Write a simple analysis script",
            task_type="code"
        )
        print(f"Started run: {run.run_id}")

        # Poll for completion
        while run.status in ("queued", "running"):
            run = client.get_run(run.run_id)
            print(f"Progress: {run.progress}%")

        if run.had_errors:
            for error in run.errors:
                print(f"Error: {error.message}")

        if run.machine_summary:
            print(f"Result: {run.machine_summary.primary_artifact}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5050",
        timeout: float = 300.0,
    ):
        """
        Initialize client.

        Args:
            base_url: Codex-Swarm API base URL
            timeout: HTTP timeout in seconds (default 5 minutes for long runs)
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def start_run(
        self,
        project_id: str,
        instructions: str,
        task_type: TaskType = "code",
        name: str | None = None,
        reference_run_id: str | None = None,
        from_run_id: str | None = None,
    ) -> RunSummary:
        """
        Start a new run.

        Args:
            project_id: Project identifier (stable across runs)
            instructions: User's task description
            task_type: Type of task (code, writing, document_analysis, etc.)
            name: Optional human-readable label
            reference_run_id: Optional run to reuse pattern from
            from_run_id: Optional run to clone workspace from

        Returns:
            RunSummary with initial status

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        payload = {
            "project_id": project_id,
            "name": name or f"{task_type} run",
            "instructions": instructions,
            "task_type": task_type,
        }

        if reference_run_id:
            payload["reference_run_id"] = reference_run_id
        if from_run_id:
            payload["from_run_id"] = from_run_id

        # Create/update project first
        self.client.put(
            f"/projects/{project_id}",
            json={
                "id": project_id,
                "name": project_id,
                "task_type": task_type,
            },
        )

        # Start run
        response = self.client.post(f"/projects/{project_id}/runs", json=payload)
        response.raise_for_status()

        return self._parse_run_response(response.json())

    def get_run(self, run_id: str) -> RunSummary:
        """
        Get run status and results.

        Args:
            run_id: Run identifier

        Returns:
            Complete run information

        Raises:
            httpx.HTTPStatusError: On API errors (404 if not found)
        """
        response = self.client.get(f"/runs/{run_id}")
        response.raise_for_status()
        return self._parse_run_response(response.json())

    def list_files(self, run_id: str) -> WorkspaceFileListing:
        """
        List files in run workspace.

        Args:
            run_id: Run identifier

        Returns:
            File listing with metadata

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        response = self.client.get(f"/runs/{run_id}/workspace/files")
        response.raise_for_status()
        data = response.json()

        return WorkspaceFileListing(
            run_id=data["run_id"],
            total_files=data["total_files"],
            files=[
                WorkspaceFile(
                    path=f["path"],
                    size_bytes=f["size_bytes"],
                    type=f["type"],
                )
                for f in data["files"]
            ],
        )

    def get_file(self, run_id: str, path: str) -> bytes:
        """
        Download file from run workspace.

        Args:
            run_id: Run identifier
            path: Workspace-relative file path

        Returns:
            File contents as bytes

        Raises:
            httpx.HTTPStatusError: On API errors (404 if not found, 403 if path traversal)
        """
        response = self.client.get(f"/runs/{run_id}/workspace/files/{path}")
        response.raise_for_status()
        return response.content

    def get_file_text(self, run_id: str, path: str, encoding: str = "utf-8") -> str:
        """
        Download text file from run workspace.

        Args:
            run_id: Run identifier
            path: Workspace-relative file path
            encoding: Text encoding (default utf-8)

        Returns:
            File contents as string

        Raises:
            httpx.HTTPStatusError: On API errors
            UnicodeDecodeError: If file is not valid text
        """
        content = self.get_file(run_id, path)
        return content.decode(encoding)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        """
        Cancel a running execution.

        Args:
            run_id: Run identifier

        Returns:
            Cancellation status

        Raises:
            httpx.HTTPStatusError: On API errors (400 if already finished)
        """
        response = self.client.post(f"/runs/{run_id}/cancel")
        response.raise_for_status()
        return response.json()

    def _parse_run_response(self, data: dict[str, Any]) -> RunSummary:
        """Parse API response into RunSummary."""
        errors = [
            RunError(
                step=e["step"],
                tool=e["tool"],
                error_type=e["error_type"],
                message=e["message"],
            )
            for e in data.get("errors", [])
        ]

        artifacts = [
            Artifact(
                id=a["id"],
                run_id=a["run_id"],
                kind=a["kind"],
                path=a["path"],
                bytes=a["bytes"],
                created_at=a["created_at"],
            )
            for a in data.get("artifacts", [])
        ]

        machine_summary = None
        if data.get("machine_summary"):
            ms = data["machine_summary"]
            machine_summary = MachineSummary(
                goal=ms["goal"],
                primary_artifact=ms.get("primary_artifact"),
                secondary_artifacts=ms.get("secondary_artifacts", []),
                execution_attempted=ms["execution_attempted"],
                execution_succeeded=ms["execution_succeeded"],
                reason_for_failure=ms.get("reason_for_failure"),
                notes=ms.get("notes"),
            )

        return RunSummary(
            run_id=data["id"],
            project_id=data["project_id"],
            task_type=data["task_type"],
            status=data["status"],
            progress=data.get("progress", 0),
            had_errors=data.get("had_errors", False),
            errors=errors,
            artifacts=artifacts,
            machine_summary=machine_summary,
            created_at=data["created_at"],
        )


# Convenience function for one-off calls
def start_run(
    project_id: str,
    instructions: str,
    task_type: TaskType = "code",
    **kwargs,
) -> RunSummary:
    """
    Convenience function to start a run.

    See CodexSwarmClient.start_run() for full documentation.
    """
    with CodexSwarmClient() as client:
        return client.start_run(
            project_id=project_id,
            instructions=instructions,
            task_type=task_type,
            **kwargs,
        )


def get_run(run_id: str) -> RunSummary:
    """
    Convenience function to get run status.

    See CodexSwarmClient.get_run() for full documentation.
    """
    with CodexSwarmClient() as client:
        return client.get_run(run_id)
