"""Domain models used throughout the editorial-fit analysis pipeline."""

from __future__ import annotations

import json
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Base class for strict domain objects with deterministic JSON serialization."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    def to_deterministic_json(self) -> str:
        """Return a canonical JSON representation with sorted keys and compact separators."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )


class DiagnosticSeverity(str, Enum):
    """Severity labels for diagnostic issues."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SeverityLevel(str, Enum):
    """Severity levels used for analyzer issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HeuristicConfidenceLabel(str, Enum):
    """Discrete confidence labels used by heuristic analyzers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SeverityMetadata(DomainModel):
    """Structured severity metadata attached to analyzer issues."""

    level: SeverityLevel
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None


class AnalyzerEvidenceSpan(DomainModel):
    """Evidence span emitted directly by analyzers with a heuristic confidence label."""

    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    heuristic_label: HeuristicConfidenceLabel
    paragraph_id: str | None = None
    sentence_id: str | None = None

    @model_validator(mode="after")
    def validate_offsets(self) -> AnalyzerEvidenceSpan:
        """Ensure evidence spans have positive width."""
        if self.end_char <= self.start_char:
            msg = "end_char must be greater than start_char"
            raise ValueError(msg)
        return self


class AnalyzerIssue(DomainModel):
    """Single issue found by an analyzer with severity metadata and optional evidence."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: SeverityMetadata
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    heuristic_confidence_label: HeuristicConfidenceLabel | None = None
    evidence_spans: tuple[AnalyzerEvidenceSpan, ...] = ()

    @staticmethod
    def _label_for_confidence(confidence: float) -> HeuristicConfidenceLabel:
        """Map a numeric confidence to a deterministic heuristic label."""
        if confidence < 0.34:
            return HeuristicConfidenceLabel.LOW
        if confidence < 0.67:
            return HeuristicConfidenceLabel.MEDIUM
        return HeuristicConfidenceLabel.HIGH

    @model_validator(mode="after")
    def validate_confidence_label(self) -> AnalyzerIssue:
        """Ensure heuristic confidence labels are present and consistent when confidence exists."""
        if self.confidence is None and self.heuristic_confidence_label is not None:
            msg = "heuristic_confidence_label requires confidence"
            raise ValueError(msg)
        if self.confidence is None:
            return self

        expected_label = self._label_for_confidence(self.confidence)
        if self.heuristic_confidence_label is None:
            self.heuristic_confidence_label = expected_label
            return self
        if self.heuristic_confidence_label != expected_label:
            msg = "heuristic_confidence_label must match confidence band"
            raise ValueError(msg)
        return self


class AnalyzerResult(DomainModel):
    """Materialized result for a single analyzer execution."""

    analyzer: str = Field(min_length=1)
    issues: tuple[AnalyzerIssue, ...]


class Sentence(DomainModel):
    """Sentence with stable identity and source text offsets."""

    sentence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_offsets(self) -> Sentence:
        """Ensure character offsets are strictly increasing."""
        if self.end_char <= self.start_char:
            msg = "end_char must be greater than start_char"
            raise ValueError(msg)
        return self


class Paragraph(DomainModel):
    """Paragraph and its sentence segmentation."""

    paragraph_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    sentences: tuple[Sentence, ...] = ()

    @model_validator(mode="after")
    def validate_boundaries(self) -> Paragraph:
        """Validate paragraph boundaries and sentence span consistency."""
        if self.end_char <= self.start_char:
            msg = "end_char must be greater than start_char"
            raise ValueError(msg)
        previous_end = self.start_char
        for sentence in self.sentences:
            if sentence.start_char < self.start_char or sentence.end_char > self.end_char:
                msg = "sentence span must be within paragraph span"
                raise ValueError(msg)
            if sentence.start_char < previous_end:
                msg = "sentence spans must be ordered and non-overlapping"
                raise ValueError(msg)
            previous_end = sentence.end_char
        return self


class Document(DomainModel):
    """Canonical in-memory draft representation."""

    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_path: str | None = None
    paragraphs: tuple[Paragraph, ...] = ()

    @model_validator(mode="after")
    def validate_structure(self) -> Document:
        """Validate paragraph ordering and in-document spans."""
        previous_end = 0
        for paragraph in self.paragraphs:
            if paragraph.start_char < 0 or paragraph.end_char > len(self.text):
                msg = "paragraph span must be within document text bounds"
                raise ValueError(msg)
            if paragraph.start_char < previous_end:
                msg = "paragraph spans must be ordered and non-overlapping"
                raise ValueError(msg)
            previous_end = paragraph.end_char
        return self


class EvidenceSpan(DomainModel):
    """Evidence span used to support a diagnostic finding."""

    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    paragraph_id: str | None = None
    sentence_id: str | None = None

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidenceSpan:
        """Ensure evidence spans have positive width."""
        if self.end_char <= self.start_char:
            msg = "end_char must be greater than start_char"
            raise ValueError(msg)
        return self


class Diagnostic(DomainModel):
    """Single analyzer output item with optional evidence spans."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: DiagnosticSeverity
    analyzer: str = Field(min_length=1)
    paragraph_id: str | None = None
    sentence_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    heuristic: bool = True
    evidence: tuple[EvidenceSpan, ...] = ()
    no_evidence_reason: str | None = None

    @model_validator(mode="after")
    def validate_evidence_requirements(self) -> Diagnostic:
        """Require either evidence spans or an explicit reason for missing evidence."""
        if not self.evidence and not self.no_evidence_reason:
            msg = "diagnostic must include evidence or no_evidence_reason"
            raise ValueError(msg)
        if self.evidence and self.no_evidence_reason:
            msg = "no_evidence_reason must be omitted when evidence is provided"
            raise ValueError(msg)
        return self


class Constraint(DomainModel):
    """Hard constraint rules used in preserve/forbid compliance checks."""

    preserve_concepts: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    max_new_sentences: int | None = Field(default=None, ge=0)
    word_count_tolerance_percent: float | None = Field(default=None, ge=0.0, le=100.0)


class AnalysisSummary(DomainModel):
    """Top-level summary values for a generated analysis report."""

    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    diagnostic_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> AnalysisSummary:
        """Ensure critical count cannot exceed total diagnostics."""
        if self.critical_count > self.diagnostic_count:
            msg = "critical_count cannot exceed diagnostic_count"
            raise ValueError(msg)
        return self


class Report(DomainModel):
    """Structured report returned by analysis and report rendering layers."""

    report_id: str = Field(min_length=1)
    document: Document
    diagnostics: tuple[Diagnostic, ...]
    constraints: Constraint | None = None
    summary: AnalysisSummary

    @model_validator(mode="after")
    def validate_summary_counts(self) -> Report:
        """Ensure summary counts align with diagnostics content."""
        if self.summary.diagnostic_count != len(self.diagnostics):
            msg = "summary diagnostic_count must match diagnostics length"
            raise ValueError(msg)
        critical_count = sum(
            1
            for item in self.diagnostics
            if item.severity == DiagnosticSeverity.CRITICAL
        )
        if self.summary.critical_count != critical_count:
            msg = "summary critical_count must match critical diagnostics"
            raise ValueError(msg)
        return self


# Backward-compatible aliases used by earlier features/tests.
ConstraintSet = Constraint
AnalysisReport = Report
