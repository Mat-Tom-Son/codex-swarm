"""Writing pattern extractor - extracts patterns from content writing workflows."""

from __future__ import annotations

import re
from typing import Any

from .base import BasePatternExtractor

# Writing-specific regex patterns
TONE_RE = re.compile(r'(?:tone|voice):\s*(\w+)', re.IGNORECASE)
AUDIENCE_RE = re.compile(r'audience:\s*([^\n,]+)', re.IGNORECASE)
STRUCTURE_RE = re.compile(r'structure:\s*([^\n,]+)', re.IGNORECASE)
WORD_COUNT_RE = re.compile(r'(\d+)\s*(?:words?|pages?)', re.IGNORECASE)
STYLE_GUIDE_RE = re.compile(r'(?:style guide|style):\s*([^\n,]+)', re.IGNORECASE)
DOC_TYPE_RE = re.compile(r'(?:article|report|paper|essay|blog post|documentation)', re.IGNORECASE)


class WritingExtractor(BasePatternExtractor):
    """Pattern extractor for writing workflows."""

    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover writing-specific variables from instruction text.

        Extracts:
        - Tone/voice (e.g., "formal", "casual")
        - Target audience
        - Document structure
        - Word count requirements
        - Style guides
        - Document type
        """
        # Extract tone
        if match := TONE_RE.search(text):
            tone = match.group(1).strip()
            variables.setdefault(
                "tone",
                {"type": "style", "example": tone},
            )

        # Extract audience
        if match := AUDIENCE_RE.search(text):
            audience = match.group(1).strip()
            variables.setdefault(
                "audience",
                {"type": "audience", "example": audience},
            )

        # Extract structure
        if match := STRUCTURE_RE.search(text):
            structure = match.group(1).strip()
            variables.setdefault(
                "structure",
                {"type": "structure", "example": structure},
            )

        # Extract word count
        if match := WORD_COUNT_RE.search(text):
            count = match.group(1)
            variables.setdefault(
                "word_count",
                {"type": "length", "example": f"{count} words"},
            )

        # Extract style guide
        if match := STYLE_GUIDE_RE.search(text):
            style = match.group(1).strip()
            variables.setdefault(
                "style_guide",
                {"type": "style_guide", "example": style},
            )

        # Extract document type
        if match := DOC_TYPE_RE.search(text):
            doc_type = match.group(0).lower()
            variables.setdefault(
                "document_type",
                {"type": "format", "example": doc_type},
            )
