"""User-friendly error handling with recovery suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class UserError(Exception):
    """User-facing error with recovery suggestion."""

    message: str
    recovery: str
    code: str
    docs_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "error": self.message,
            "suggestion": self.recovery,
            "code": self.code,
        }
        if self.docs_url:
            result["docs"] = self.docs_url
        return result


# Common errors with recovery suggestions
CODEX_NOT_FOUND = UserError(
    message="Codex CLI is not installed or not in your PATH",
    recovery="Install Codex CLI from https://docs.claude.com/claude-code or ensure it's in your PATH",
    code="CODEX_CLI_MISSING",
    docs_url="https://docs.claude.com/claude-code",
)

CODEX_AUTH_FAILED = UserError(
    message="Codex CLI authentication failed",
    recovery="Set OPENAI_API_KEY environment variable in your .env file or run 'codex login'",
    code="CODEX_AUTH_REQUIRED",
    docs_url="https://docs.claude.com/claude-code/authentication",
)

OPENAI_KEY_MISSING = UserError(
    message="OpenAI API key not configured",
    recovery="Set OPENAI_API_KEY in your .env file or set CROSS_RUN_FAKE_SWARM=1 for offline mode",
    code="OPENAI_KEY_MISSING",
)

WORKSPACE_NOT_FOUND = UserError(
    message="Source workspace not found for cloning",
    recovery="Check that the source run ID is correct, or start without --from-run-id",
    code="WORKSPACE_MISSING",
)

PROJECT_NOT_FOUND = UserError(
    message="Project not found",
    recovery="Create the project first or check the project ID spelling",
    code="PROJECT_NOT_FOUND",
)

RUN_NOT_FOUND = UserError(
    message="Run not found",
    recovery="Check the run ID is correct. List runs with: ./run.sh crossrun list",
    code="RUN_NOT_FOUND",
)

PATTERN_EXTRACTION_FAILED = UserError(
    message="Failed to extract pattern from run",
    recovery="The run may not have completed successfully. Check run status and logs.",
    code="PATTERN_EXTRACTION_FAILED",
)

RUNNER_UNAVAILABLE = UserError(
    message="Swarm runner service is not available",
    recovery="Start the runner service with: ./run.sh crossrun services",
    code="RUNNER_UNAVAILABLE",
)


def parse_error_notes(notes: list[str]) -> UserError | None:
    """Parse error notes from codex_exec and return appropriate UserError."""
    if not notes:
        return None

    for note in notes:
        if "codex-cli-not-found" in note:
            return CODEX_NOT_FOUND
        if "codex-login-failed" in note or "codex-login-missing-key" in note:
            return CODEX_AUTH_FAILED

    return None
