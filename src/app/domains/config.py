"""
Domain configuration for different workflow types.

Each domain defines:
- Description of the workflow type
- Pattern extraction preferences
- Artifact type priorities
- Default Swarm instruction template
"""

from dataclasses import dataclass
from typing import Literal

TaskType = Literal["code", "research", "writing", "data_analysis", "document_processing"]


@dataclass
class DomainConfig:
    """Configuration for a specific domain/workflow type."""

    name: str
    description: str
    instruction_template: str  # File name in domains/instructions/
    pattern_extractor: str  # Extractor class name
    primary_artifact_types: list[str]  # Expected output artifact types
    workspace_required: bool = True


DOMAIN_CONFIGS: dict[TaskType, DomainConfig] = {
    "code": DomainConfig(
        name="Code Development",
        description="Software development, scripting, and coding tasks",
        instruction_template="code_mode.txt",
        pattern_extractor="CodeExtractor",
        primary_artifact_types=["codex-jsonl", "diff-summary"],
        workspace_required=True,
    ),
    "research": DomainConfig(
        name="Research",
        description="Literature review, web research, citation gathering, and synthesis",
        instruction_template="research_mode.txt",
        pattern_extractor="ResearchExtractor",
        primary_artifact_types=["markdown", "codex-jsonl", "json"],
        workspace_required=True,
    ),
    "writing": DomainConfig(
        name="Long-Form Writing",
        description="Articles, reports, documentation, and other long-form content",
        instruction_template="writing_mode.txt",
        pattern_extractor="WritingExtractor",
        primary_artifact_types=["markdown", "docx", "pdf", "codex-jsonl"],
        workspace_required=True,
    ),
    "data_analysis": DomainConfig(
        name="Data Analysis",
        description="Python analysis, data visualization, statistical computing",
        instruction_template="data_mode.txt",
        pattern_extractor="DataExtractor",
        primary_artifact_types=["ipynb", "csv", "png", "json", "codex-jsonl"],
        workspace_required=True,
    ),
    "document_processing": DomainConfig(
        name="Document Processing",
        description="Batch document conversion, formatting, and transformation",
        instruction_template="document_mode.txt",
        pattern_extractor="DocumentExtractor",
        primary_artifact_types=["docx", "pdf", "markdown", "codex-jsonl"],
        workspace_required=True,
    ),
}


def get_domain_config(task_type: str) -> DomainConfig:
    """Get domain configuration for a task type."""
    return DOMAIN_CONFIGS.get(task_type, DOMAIN_CONFIGS["code"])  # type: ignore


def list_task_types() -> list[tuple[str, str]]:
    """List all available task types with descriptions."""
    return [(k, v.description) for k, v in DOMAIN_CONFIGS.items()]

# Backwards compatibility for older callers
list_project_types = list_task_types
