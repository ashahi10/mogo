"""Unit tests for evaluate metric computations."""

from __future__ import annotations

from evaluate import EvalResult, compute_metrics
from models import DecisionOutput
from validator import compute_guardrail_indicators, confidence_calibration_snapshot


def test_compute_metrics_accuracy_counts():
    """compute_metrics should calculate accuracy and decision counts correctly."""
    results = [
        EvalResult("CASE-001", "straightforward", "APPROVE", "APPROVE", 0.9, False),
        EvalResult("CASE-002", "straightforward", "DENY", "DENY", 0.8, False),
        EvalResult("CASE-003", "straightforward", "APPROVE", "DENY", 0.6, False),
        EvalResult("CASE-004", "straightforward", "DENY", "DENY", 0.9, False),
    ]
    metrics = compute_metrics(results)
    assert metrics.accuracy == 0.75
    assert metrics.approve_count == 1
    assert metrics.deny_count == 3
    assert metrics.escalate_count == 0


def test_compute_metrics_ambiguous_escalation_rate():
    """compute_metrics should compute ambiguous escalation percentage from raw counts."""
    results = [
        EvalResult("CASE-101", "ambiguous", "ESCALATE", "ESCALATE", 0.7, False),
        EvalResult("CASE-102", "ambiguous", "ESCALATE", "ESCALATE", 0.6, False),
        EvalResult("CASE-103", "ambiguous", "ESCALATE", "ESCALATE", 0.5, False),
        EvalResult("CASE-104", "ambiguous", "ESCALATE", "DENY", 0.8, False),
    ]
    metrics = compute_metrics(results)
    assert metrics.ambiguous_escalated_pct == 0.75


def test_guardrail_indicators_detect_citation_drift_in_audit():
    """compute_guardrail_indicators should count outputs whose audit notes stripped citations."""
    output = DecisionOutput(
        case_id="CASE-001",
        decision="APPROVE",
        confidence=0.9,
        policy_citations=[{"policy_id": "POL-001", "reason": "ok"}],
        audit_log={
            "retrieved_policies": ["POL-001"],
            "retrieval_score": 0.7,
            "timestamp": "2026-01-01T00:00:00Z",
            "retry_attempted": False,
            "error_detail": "Removed non-retrieved policy citations: POL-999",
        },
    )
    indicators = compute_guardrail_indicators([output], None)
    assert indicators.citation_drift_count == 1
    assert indicators.citation_drift_rate == 1.0
    assert indicators.citation_drift_severity == "high"


def test_confidence_calibration_snapshot_buckets_with_accuracy():
    """confidence_calibration_snapshot should bucket confidences and score label accuracy."""
    outputs = [
        DecisionOutput(
            case_id="CASE-901",
            decision="APPROVE",
            confidence=0.85,
            policy_citations=[{"policy_id": "POL-001", "reason": "ok"}],
            audit_log={
                "retrieved_policies": ["POL-001"],
                "retrieval_score": 0.7,
                "timestamp": "2026-01-01T00:00:00Z",
                "retry_attempted": False,
            },
        ),
        DecisionOutput(
            case_id="CASE-902",
            decision="DENY",
            confidence=0.85,
            policy_citations=[{"policy_id": "POL-001", "reason": "no"}],
            audit_log={
                "retrieved_policies": ["POL-001"],
                "retrieval_score": 0.7,
                "timestamp": "2026-01-01T00:00:00Z",
                "retry_attempted": False,
            },
        ),
    ]
    expected = {"CASE-901": "APPROVE", "CASE-902": "APPROVE"}
    snap = confidence_calibration_snapshot(outputs, expected)
    high = snap["0.80-1.00"]
    assert int(high["count"]) == 2
    assert high["accuracy"] == 0.5
