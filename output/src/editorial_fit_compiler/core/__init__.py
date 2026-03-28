"""Core package for the Editorial Fit Compiler architecture."""

from .config import ConfigConstraints, ConfigPreferences, UserConfig, load_user_config
from .models import (
    AnalysisReport,
    AnalysisSummary,
    Constraint,
    ConstraintSet,
    Diagnostic,
    DiagnosticSeverity,
    Document,
    EvidenceSpan,
    Paragraph,
    Report,
    Sentence,
)

__all__ = [
    "AnalysisReport",
    "AnalysisSummary",
    "ConfigConstraints",
    "ConfigPreferences",
    "Constraint",
    "ConstraintSet",
    "Diagnostic",
    "DiagnosticSeverity",
    "Document",
    "EvidenceSpan",
    "Paragraph",
    "Report",
    "Sentence",
    "UserConfig",
    "load_user_config",
]
