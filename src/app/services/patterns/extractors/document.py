"""Document processing pattern extractor - extracts patterns from document workflows."""

from __future__ import annotations

import re
from typing import Any

from .base import BasePatternExtractor

# Document processing regex patterns
FORMAT_CONVERSION_RE = re.compile(
    r'(?:convert|transform)\s+(\w+)\s+(?:to|into|as)\s+(\w+)', re.IGNORECASE
)
BATCH_PATTERN_RE = re.compile(r'(?:all|each|every)\s+(\w+)', re.IGNORECASE)
TEMPLATE_RE = re.compile(r'(?:template|format):\s*([^\n,]+)', re.IGNORECASE)
INPUT_DIR_RE = re.compile(r'(?:input|source)\s+(?:directory|folder):\s*([^\s,]+)', re.IGNORECASE)
OUTPUT_DIR_RE = re.compile(r'(?:output|destination)\s+(?:directory|folder):\s*([^\s,]+)', re.IGNORECASE)


class DocumentExtractor(BasePatternExtractor):
    """Pattern extractor for document processing workflows."""

    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover document processing variables from instruction text.

        Extracts:
        - Format conversions (e.g., "convert DOCX to PDF")
        - Batch processing patterns
        - Template references
        - Input/output directories
        """
        # Extract format conversion patterns
        if match := FORMAT_CONVERSION_RE.search(text):
            source_format = match.group(1).strip()
            target_format = match.group(2).strip()
            variables.setdefault(
                "source_format",
                {"type": "format", "example": source_format},
            )
            variables.setdefault(
                "target_format",
                {"type": "format", "example": target_format},
            )

        # Extract batch processing patterns
        if match := BATCH_PATTERN_RE.search(text):
            item_type = match.group(1).strip()
            variables.setdefault(
                "batch_item",
                {"type": "item", "example": item_type},
            )

        # Extract template references
        if match := TEMPLATE_RE.search(text):
            template = match.group(1).strip()
            variables.setdefault(
                "template",
                {"type": "template", "example": template},
            )

        # Extract input directory
        if match := INPUT_DIR_RE.search(text):
            input_dir = match.group(1).strip()
            variables.setdefault(
                "input_dir",
                {"type": "path", "example": input_dir},
            )

        # Extract output directory
        if match := OUTPUT_DIR_RE.search(text):
            output_dir = match.group(1).strip()
            variables.setdefault(
                "output_dir",
                {"type": "path", "example": output_dir},
            )
