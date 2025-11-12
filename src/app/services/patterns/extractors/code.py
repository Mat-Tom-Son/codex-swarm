"""Code pattern extractor - extracts patterns from software development workflows."""

from __future__ import annotations

import re
from typing import Any

from .base import BasePatternExtractor

# Code-specific regex patterns
FILE_RANGE_RE = re.compile(r"(\w+)-(\d+)\s*(?:to|through|:)\s*(\w+)-?(\d+)", re.IGNORECASE)
SUB_RE = re.compile(r"replace\s+(.+?)\s+with\s+(?:contents\s+from\s+)?(.+)", re.IGNORECASE)
FILE_REF_RE = re.compile(r"([\w./-]+\.(?:txt|md|csv|json|py|js|ts|go|rs|java))", re.IGNORECASE)


class CodeExtractor(BasePatternExtractor):
    """Pattern extractor for code development workflows."""

    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover code-specific variables from instruction text.

        Extracts:
        - File range patterns (e.g., "file1-10 to file2-20")
        - Text substitution patterns (e.g., "replace X with Y")
        - File references (various code file extensions)
        """
        # Extract file range patterns
        if match := FILE_RANGE_RE.search(text):
            variables.setdefault(
                "fileRange",
                {"type": "range", "example": match.group(0)},
            )

        # Extract substitution patterns
        if match := SUB_RE.search(text):
            placeholder = match.group(1).strip()
            source = match.group(2).strip()
            if placeholder:
                variables.setdefault("placeholder", {"type": "text", "example": placeholder})
            if source:
                variables.setdefault("source", {"type": "text", "example": source})

        # Extract file references
        if match := FILE_REF_RE.search(text):
            variables.setdefault(
                "file",
                {"type": "file", "example": match.group(1)},
            )
