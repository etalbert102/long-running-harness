"""Tests for strict domain models in the core package."""

from __future__ import annotations

import pytest

from editorial_fit_compiler.core.models import (
    AnalysisReport,
    AnalysisSummary,
    AnalyzerEvidenceSpan,
    AnalyzerIssue,
    AnalyzerResult,
    Constraint,
    ConstraintSet,
    Diagnostic,
    DiagnosticSeverity,
    Document,
    EvidenceSpan,
    HeuristicConfidenceLabel,
    Paragraph,
    Report,
    Sentence,
    SeverityLevel,
    SeverityMetadata,
)
from pydantic import ValidationError


def _valid_document() -> Document:
    """Create a valid document fixture."""
    return Document.model_validate(
        {
            "document_id": "doc-1",
            "text": "Alpha beta. Gamma delta.",
            "paragraphs": [
                {
                    "paragraph_id": "p1",
                    "text": "Alpha beta. Gamma delta.",
                    "start_char": 0,
                    "end_char": 24,
                    "sentences": [
                        {
                            "sentence_id": "s1",
                            "text": "Alpha beta.",
                            "start_char": 0,
                            "end_char": 11,
                        },
                        {
                            "sentence_id": "s2",
                            "text": "Gamma delta.",
                            "start_char": 12,
                            "end_char": 24,
                        },
                    ],
                }
            ],
        }
    )


def test_valid_domain_models_parse_and_serialize_deterministically() -> None:
    """Valid nested inputs should parse and serialize with stable JSON output."""
    document = _valid_document()
    diagnostic = Diagnostic.model_validate(
        {
            "code": "abstract_opening",
            "message": "Opening is highly abstract.",
            "severity": "warning",
            "analyzer": "rhetoric",
            "evidence": [
                {
                    "text": "Alpha beta",
                    "start_char": 0,
                    "end_char": 10,
                    "paragraph_id": "p1",
                    "sentence_id": "s1",
                }
            ],
        }
    )
    constraints = Constraint.model_validate(
        {
            "preserve_concepts": ["Behavioral Compression"],
            "forbid": ["em_dash", "citations"],
            "max_new_sentences": 2,
            "word_count_tolerance_percent": 5.0,
        }
    )
    report = Report.model_validate(
        {
            "report_id": "report-1",
            "document": document.model_dump(mode="json"),
            "diagnostics": [diagnostic.model_dump(mode="json")],
            "constraints": constraints.model_dump(mode="json"),
            "summary": {
                "overall_score": 78.5,
                "diagnostic_count": 1,
                "critical_count": 0,
            },
        }
    )

    serialized_first = report.to_deterministic_json()
    serialized_second = report.to_deterministic_json()

    assert serialized_first == serialized_second
    assert '"severity":"warning"' in serialized_first


def test_compatibility_alias_models_match_canonical_behavior() -> None:
    """Backwards-compatible aliases should preserve strict validation and structure."""
    constraints = ConstraintSet.model_validate(
        {
            "preserve_concepts": ["Authority Topology"],
            "forbid": ["citations"],
        }
    )
    report = AnalysisReport.model_validate(
        {
            "report_id": "report-compat",
            "document": _valid_document().model_dump(mode="json"),
            "diagnostics": [],
            "constraints": constraints.model_dump(mode="json"),
            "summary": {
                "overall_score": 100.0,
                "diagnostic_count": 0,
                "critical_count": 0,
            },
        }
    )

    assert report.constraints is not None
    assert report.constraints.forbid == ("citations",)


def test_invalid_document_shape_is_rejected() -> None:
    """Invalid nested spans should be rejected by strict validators."""
    with pytest.raises(ValidationError):
        Document.model_validate(
            {
                "document_id": "doc-invalid",
                "text": "Short text",
                "paragraphs": [
                    {
                        "paragraph_id": "p1",
                        "text": "Short text",
                        "start_char": 0,
                        "end_char": 50,
                        "sentences": [],
                    }
                ],
            }
        )


def test_invalid_sentence_offsets_are_rejected() -> None:
    """Sentence model should reject non-increasing offsets."""
    with pytest.raises(ValidationError):
        Sentence.model_validate(
            {
                "sentence_id": "s-bad",
                "text": "Bad sentence",
                "start_char": 10,
                "end_char": 10,
            }
        )


def test_invalid_diagnostic_shape_requires_evidence_or_reason() -> None:
    """Diagnostic entries must include evidence spans or an explicit reason."""
    with pytest.raises(ValidationError):
        Diagnostic.model_validate(
            {
                "code": "missing_evidence",
                "message": "No supporting span",
                "severity": DiagnosticSeverity.WARNING,
                "analyzer": "style",
            }
        )


def test_invalid_extra_fields_are_rejected() -> None:
    """Models should reject unknown fields for strict schema behavior."""
    with pytest.raises(ValidationError):
        ConstraintSet.model_validate(
            {
                "preserve_concepts": ["Authority Topology"],
                "unknown_field": True,
            }
        )


def test_report_summary_counts_must_match_diagnostics() -> None:
    """Report-level summary counts must align with diagnostic entries."""
    document = _valid_document()
    diagnostic = Diagnostic(
        code="critical_issue",
        message="Critical issue.",
        severity=DiagnosticSeverity.CRITICAL,
        analyzer="structure",
        no_evidence_reason="Derived aggregate metric",
    )
    summary = AnalysisSummary(overall_score=55.0, diagnostic_count=0, critical_count=0)

    with pytest.raises(ValidationError):
        AnalysisReport(
            report_id="report-invalid-summary",
            document=document,
            diagnostics=(diagnostic,),
            summary=summary,
        )


def test_evidence_span_model_validates_offsets() -> None:
    """Evidence spans should enforce positive-width text offsets."""
    with pytest.raises(ValidationError):
        EvidenceSpan(
            text="bad",
            start_char=5,
            end_char=4,
        )


def test_paragraph_model_rejects_overlapping_sentence_spans() -> None:
    """Paragraph should reject overlapping sentence boundaries."""
    with pytest.raises(ValidationError):
        Paragraph.model_validate(
            {
                "paragraph_id": "p-bad",
                "text": "Some text",
                "start_char": 0,
                "end_char": 9,
                "sentences": [
                    {"sentence_id": "s1", "text": "Some", "start_char": 0, "end_char": 4},
                    {"sentence_id": "s2", "text": "text", "start_char": 3, "end_char": 8},
                ],
            }
        )


def test_numeric_fields_reject_boolean_values() -> None:
    """Boolean values should not be accepted for numeric constrained fields."""
    with pytest.raises(ValidationError):
        Sentence.model_validate(
            {
                "sentence_id": "s-bool",
                "text": "Boolean offset",
                "start_char": True,
                "end_char": 5,
            }
        )

    with pytest.raises(ValidationError):
        AnalysisSummary.model_validate(
            {
                "overall_score": True,
                "diagnostic_count": 0,
                "critical_count": 0,
            }
        )


def test_analyzer_result_materializes_issue_with_severity_and_labeled_evidence() -> None:
    """Analyzer result should include severity metadata and evidence spans with heuristic labels."""
    result = AnalyzerResult.model_validate(
        {
            "analyzer": "abstraction_density",
            "issues": [
                {
                    "code": "abstract_cluster",
                    "message": "Cluster of abstract terms in opener",
                    "severity": {
                        "level": "high",
                        "score": 0.91,
                        "rationale": "Found dense concentration in first paragraph",
                    },
                    "confidence": 0.72,
                    "evidence_spans": [
                        {
                            "text": "systemic architecture",
                            "start_char": 3,
                            "end_char": 23,
                            "heuristic_label": "medium",
                            "paragraph_id": "p1",
                        }
                    ],
                }
            ],
        }
    )

    issue = result.issues[0]
    assert issue.severity.level == SeverityLevel.HIGH
    assert issue.heuristic_confidence_label == HeuristicConfidenceLabel.HIGH
    assert issue.evidence_spans[0].heuristic_label == HeuristicConfidenceLabel.MEDIUM


def test_analyzer_issue_allows_optional_evidence_spans() -> None:
    """Analyzer issues should allow no evidence spans when a finding is aggregate."""
    issue = AnalyzerIssue.model_validate(
        {
            "code": "sentence_uniformity",
            "message": "Sentences are uniformly narrow in length",
            "severity": {"level": "medium", "score": 0.65},
            "confidence": 0.66,
            "evidence_spans": [],
        }
    )

    assert issue.evidence_spans == ()
    assert issue.heuristic_confidence_label == HeuristicConfidenceLabel.MEDIUM


def test_analyzer_issue_rejects_mismatched_heuristic_confidence_band() -> None:
    """Explicit heuristic confidence labels must match the confidence-derived band."""
    with pytest.raises(ValidationError):
        AnalyzerIssue.model_validate(
            {
                "code": "opener_template_repeat",
                "message": "Template repeats in nearby sentences",
                "severity": SeverityMetadata(level=SeverityLevel.MEDIUM).model_dump(
                    mode="json"
                ),
                "confidence": 0.2,
                "heuristic_confidence_label": "high",
            }
        )


def test_analyzer_evidence_span_rejects_invalid_offsets() -> None:
    """Analyzer evidence spans should enforce positive-width offsets."""
    with pytest.raises(ValidationError):
        AnalyzerEvidenceSpan.model_validate(
            {
                "text": "invalid",
                "start_char": 9,
                "end_char": 2,
                "heuristic_label": "low",
            }
        )
