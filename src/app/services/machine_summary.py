"""
Machine summary generation for DraftPunk integration.

This module creates structured, machine-friendly summaries of run outcomes
based on logged steps, artifacts, and errors. No LLM calls - just deterministic
data transformation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import Artifact, Run, Step

logger = logging.getLogger(__name__)


def generate_machine_summary(
    run: Run,
    steps: list[Step],
    artifacts: list[Artifact],
    workspace_path: Path,
) -> dict[str, Any]:
    """
    Generate a machine-friendly summary of a run's outcome.

    This is deterministic - no LLM calls, just analyzing structured data.

    Args:
        run: The run model
        steps: All execution steps
        artifacts: All artifacts produced
        workspace_path: Path to run workspace

    Returns:
        Machine summary dict matching MachineSummary schema
    """
    # Extract goal from system instructions (last line is user prompt)
    goal = _extract_goal(run.system_instructions or "")

    # Identify artifacts
    primary_artifact, secondary_artifacts = _identify_artifacts(artifacts, workspace_path)

    # Determine execution status
    execution_attempted = len(steps) > 0
    execution_succeeded = run.status == "succeeded"

    # Analyze failure reasons
    reason_for_failure = None
    notes = None
    if not execution_succeeded:
        reason_for_failure, notes = _analyze_failure(run, steps)

    return {
        "goal": goal,
        "primary_artifact": primary_artifact,
        "secondary_artifacts": secondary_artifacts,
        "execution_attempted": execution_attempted,
        "execution_succeeded": execution_succeeded,
        "reason_for_failure": reason_for_failure,
        "notes": notes,
    }


def _extract_goal(system_instructions: str) -> str:
    """Extract user's goal from system instructions."""
    if not system_instructions:
        return "No goal specified"

    # System instructions format: [pattern_block] + base_prompt + user_prompt
    # User prompt is the last meaningful paragraph
    lines = system_instructions.strip().split("\n")

    # Work backwards to find user's actual request
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line and not line.startswith("<") and not line.startswith("You are"):
            return line

    return system_instructions[:200]  # Fallback: first 200 chars


def _identify_artifacts(
    artifacts: list[Artifact],
    workspace_path: Path,
) -> tuple[str | None, list[str]]:
    """
    Identify primary and secondary artifacts.

    Primary artifact: Most important output file (first markdown, or first non-log)
    Secondary artifacts: Other notable outputs

    Returns:
        (primary_artifact_path, secondary_artifact_paths)
    """
    if not artifacts:
        return None, []

    # Separate execution logs from content artifacts
    content_artifacts = [
        a for a in artifacts
        if a.kind not in ("codex-jsonl", "diff-summary")
    ]

    # If no content artifacts, look for actual workspace files
    workspace_files = []
    if workspace_path.exists():
        workspace_files = _list_workspace_outputs(workspace_path)

    # Primary artifact heuristics:
    # 1. First markdown file (common output format)
    # 2. First workspace file that's not a log
    # 3. First artifact of any kind

    primary = None
    secondary = []

    # Check content artifacts first
    markdown_artifacts = [a for a in content_artifacts if a.kind == "markdown"]
    if markdown_artifacts:
        primary = _relative_path(markdown_artifacts[0].path, workspace_path)
        secondary = [_relative_path(a.path, workspace_path) for a in content_artifacts[1:]]
    elif content_artifacts:
        primary = _relative_path(content_artifacts[0].path, workspace_path)
        secondary = [_relative_path(a.path, workspace_path) for a in content_artifacts[1:]]

    # Check workspace files
    elif workspace_files:
        primary = workspace_files[0]
        secondary = workspace_files[1:]

    return primary, secondary[:5]  # Limit to 5 secondary artifacts


def _list_workspace_outputs(workspace_path: Path) -> list[str]:
    """List notable output files in workspace."""
    outputs = []

    # Common output patterns
    output_extensions = {".md", ".txt", ".html", ".pdf", ".docx", ".csv", ".json"}

    for file_path in workspace_path.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(workspace_path)

        # Skip .git internals
        if str(rel_path).startswith(".git/"):
            continue

        # Skip hidden files
        if file_path.name.startswith("."):
            continue

        # Include files with output-like extensions
        if file_path.suffix in output_extensions:
            outputs.append(str(rel_path))

    return sorted(outputs)[:10]  # Limit to 10 files


def _relative_path(absolute_path: str, workspace_path: Path) -> str:
    """Convert absolute artifact path to workspace-relative path."""
    try:
        path = Path(absolute_path)
        if path.is_relative_to(workspace_path):
            return str(path.relative_to(workspace_path))
    except (ValueError, OSError):
        pass
    return absolute_path


def _analyze_failure(run: Run, steps: list[Step]) -> tuple[str | None, str | None]:
    """
    Analyze why a run failed.

    Returns:
        (reason_for_failure, notes)
    """
    if run.status == "cancelled":
        return "cancelled", "Run was cancelled by user"

    if run.status != "failed":
        return None, None

    # Check for error signals in steps
    tool_steps = [s for s in steps if s.role == "tool"]

    # Look for failed tool executions
    failed_tools = [s for s in tool_steps if s.outcome_ok is False]

    if failed_tools:
        last_failure = failed_tools[-1]

        # Parse error notes if available
        error_type = "tool_failure"
        notes_text = None

        if last_failure.outcome_notes_json:
            try:
                notes = json.loads(last_failure.outcome_notes_json)
                if isinstance(notes, list) and notes:
                    notes_text = "; ".join(str(n) for n in notes)

                    # Classify error type
                    notes_lower = notes_text.lower()
                    if "permission" in notes_lower or "denied" in notes_lower:
                        error_type = "permission_error"
                    elif "not found" in notes_lower or "missing" in notes_lower:
                        error_type = "missing_dependency"
                    elif "timeout" in notes_lower:
                        error_type = "timeout"
            except (json.JSONDecodeError, TypeError):
                pass

        return error_type, notes_text or f"Tool {last_failure.tool_name} failed"

    # Check for errors in run.errors_json
    if run.errors_json:
        try:
            errors = json.loads(run.errors_json)
            if errors and isinstance(errors, list):
                first_error = errors[0]
                return first_error.get("error_type", "unknown_error"), first_error.get("message")
        except (json.JSONDecodeError, TypeError):
            pass

    # Generic failure
    return "execution_error", "Run failed without specific error details"
