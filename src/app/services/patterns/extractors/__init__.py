"""Pattern extractors for different domains."""

from .base import BasePatternExtractor
from .code import CodeExtractor
from .data import DataExtractor
from .document import DocumentExtractor
from .research import ResearchExtractor
from .writing import WritingExtractor

__all__ = [
    "BasePatternExtractor",
    "CodeExtractor",
    "ResearchExtractor",
    "WritingExtractor",
    "DataExtractor",
    "DocumentExtractor",
]

# Registry mapping extractor names to classes
EXTRACTOR_REGISTRY = {
    "CodeExtractor": CodeExtractor,
    "ResearchExtractor": ResearchExtractor,
    "WritingExtractor": WritingExtractor,
    "DataExtractor": DataExtractor,
    "DocumentExtractor": DocumentExtractor,
}


def get_extractor(name: str) -> type[BasePatternExtractor]:
    """Get an extractor class by name."""
    return EXTRACTOR_REGISTRY.get(name, CodeExtractor)
