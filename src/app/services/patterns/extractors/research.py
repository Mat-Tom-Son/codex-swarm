"""Research pattern extractor - extracts patterns from research workflows."""

from __future__ import annotations

import re
from typing import Any

from .base import BasePatternExtractor

# Research-specific regex patterns
CITATION_RE = re.compile(r'\[(\d+)\]|\(([^)]+,\s*\d{4})\)', re.IGNORECASE)
URL_RE = re.compile(r'https?://[^\s]+', re.IGNORECASE)
QUERY_RE = re.compile(r'search\s+(?:for|query)?:?\s*["\']?([^"\']+)["\']?', re.IGNORECASE)
SOURCE_DOC_RE = re.compile(r'(?:source|document|paper|article):\s*([^\n,]+)', re.IGNORECASE)
TOPIC_RE = re.compile(r'(?:topic|subject|area):\s*([^\n,]+)', re.IGNORECASE)


class ResearchExtractor(BasePatternExtractor):
    """Pattern extractor for research workflows."""

    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover research-specific variables from instruction text.

        Extracts:
        - Citations (e.g., "[1]" or "(Author, 2023)")
        - URLs for web sources
        - Search queries
        - Source documents
        - Research topics
        """
        # Extract citations
        if match := CITATION_RE.search(text):
            citation = match.group(1) or match.group(2)
            variables.setdefault(
                "citation",
                {"type": "citation", "example": citation},
            )

        # Extract URLs
        if match := URL_RE.search(text):
            variables.setdefault(
                "url",
                {"type": "url", "example": match.group(0)[:50]},
            )

        # Extract search queries
        if match := QUERY_RE.search(text):
            query = match.group(1).strip()
            variables.setdefault(
                "search_query",
                {"type": "query", "example": query},
            )

        # Extract source documents
        if match := SOURCE_DOC_RE.search(text):
            source = match.group(1).strip()
            variables.setdefault(
                "source_doc",
                {"type": "document", "example": source},
            )

        # Extract research topics
        if match := TOPIC_RE.search(text):
            topic = match.group(1).strip()
            variables.setdefault(
                "research_topic",
                {"type": "topic", "example": topic},
            )
