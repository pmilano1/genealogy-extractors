"""Genealogy Extractors - Extract records from multiple genealogy sources."""

__version__ = "0.1.0"

from .extractors import (
    BaseRecordExtractor,
    AncestryExtractor,
    ANOMExtractor,
    AntenatiExtractor,
    FindAGraveExtractor,
    GeneanetExtractor,
    MatchIDExtractor,
)
from .debug_log import debug, info, warn, error, set_verbose

__all__ = [
    "__version__",
    "BaseRecordExtractor",
    "AncestryExtractor",
    "ANOMExtractor",
    "AntenatiExtractor",
    "FindAGraveExtractor",
    "GeneanetExtractor",
    "MatchIDExtractor",
    "debug",
    "info",
    "warn",
    "error",
    "set_verbose",
]