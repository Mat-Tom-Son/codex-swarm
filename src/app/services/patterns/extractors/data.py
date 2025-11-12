"""Data analysis pattern extractor - extracts patterns from data analysis workflows."""

from __future__ import annotations

import re
from typing import Any

from .base import BasePatternExtractor

# Data analysis regex patterns
DATAFRAME_OP_RE = re.compile(
    r'(?:filter|group|merge|join|sort|aggregate|pivot)\s+(?:by\s+)?([^\s,]+)', re.IGNORECASE
)
CHART_TYPE_RE = re.compile(
    r'(bar|line|scatter|histogram|pie|box|violin|heatmap)\s+(?:chart|plot|graph)', re.IGNORECASE
)
DATASET_RE = re.compile(r'(?:dataset|data file|csv|excel):\s*([^\n,]+)', re.IGNORECASE)
COLUMN_RE = re.compile(r'column[s]?:\s*([^\n,]+)', re.IGNORECASE)
STATISTICAL_RE = re.compile(
    r'(mean|median|std|variance|correlation|regression|p-value)', re.IGNORECASE
)


class DataExtractor(BasePatternExtractor):
    """Pattern extractor for data analysis workflows."""

    def discover_variables(self, text: str, variables: dict[str, Any]) -> None:
        """
        Discover data analysis variables from instruction text.

        Extracts:
        - DataFrame operations (filter, group, merge, etc.)
        - Chart types
        - Dataset references
        - Column names
        - Statistical methods
        """
        # Extract dataframe operations
        if match := DATAFRAME_OP_RE.search(text):
            operation = match.group(0).strip()
            variables.setdefault(
                "data_operation",
                {"type": "operation", "example": operation},
            )

        # Extract chart types
        if match := CHART_TYPE_RE.search(text):
            chart_type = match.group(1).lower()
            variables.setdefault(
                "chart_type",
                {"type": "visualization", "example": f"{chart_type} chart"},
            )

        # Extract dataset references
        if match := DATASET_RE.search(text):
            dataset = match.group(1).strip()
            variables.setdefault(
                "dataset",
                {"type": "file", "example": dataset},
            )

        # Extract column names
        if match := COLUMN_RE.search(text):
            columns = match.group(1).strip()
            variables.setdefault(
                "columns",
                {"type": "column", "example": columns},
            )

        # Extract statistical methods
        if match := STATISTICAL_RE.search(text):
            method = match.group(1).lower()
            variables.setdefault(
                "statistical_method",
                {"type": "statistic", "example": method},
            )
