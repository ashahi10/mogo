"""Unit tests for evaluate metric computations."""

from __future__ import annotations

from evaluate import EvalResult, compute_metrics


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
