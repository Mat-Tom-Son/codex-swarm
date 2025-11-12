"""Base pattern extractor class."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from ....models import Step


class BasePatternExtractor(ABC):
    """Base class for domain-specific pattern extractors."""

    @abstractmethod
    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover and extract variables from instruction text.

        Args:
            text: The instruction text to analyze
            variables: Dictionary to populate with discovered variables
        """
        pass

    def normalize_instruction(self, text: str) -> str:
        """
        Normalize instruction text for pattern extraction.

        Default implementation: collapse whitespace, limit to 160 chars.
        Override if domain needs different normalization.
        """
        cleaned = re.sub(r"\s+", " ", text.strip())
        return cleaned[:160]

    def should_include_step(self, step: Step) -> bool:
        """
        Determine if a step should be included in the pattern.

        Default implementation: include assistant/tool steps with outcome_ok != False.
        Override for domain-specific filtering.
        """
        if step.role not in {"assistant", "tool"}:
            return False
        if step.outcome_ok is False:
            return False
        return True

    def extract_summary(self, instructions: list[str]) -> str:
        """
        Generate a summary from instructions.

        Default implementation: concatenate first 2 instructions.
        Override for domain-specific summarization.
        """
        summary = " ".join(instructions[:2])
        return summary[:200]
