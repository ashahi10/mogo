"""Stress tests for validator/retriever resilience under adversarial conditions."""

from __future__ import annotations

import json

from models import Case, DecisionOutput, Policy
from retriever import PolicyRetriever, build_retrieval_query
from tests.stress.harness import malformed_response_cases
from validator import EscalationChecker, parse_and_validate, validate_with_retry


def _sample_case() -> Case:
    return Case(
        case_id="CASE-777",
        summary="Adversarial stress case for robustness checks.",
        attributes={
            "case_type": "payout_review",
            "payout_amount": 1200.0,
            "identity_verified": True,
            "verified_name": "Ari Shah",
            "account_holder_name": "Ari Shah",
            "recent_profile_changes": 1,
            "high_risk_flag": False,
            "account_age_days": 220,
            "missing_fields": [],
            "transaction_velocity": 2,
        },
        expected_decision="APPROVE",
        difficulty="straightforward",
    )


def test_parse_and_validate_handles_malformed_llm_outputs():
    """Validator should robustly parse/flag malformed LLM outputs without raising."""
    retrieved = [Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e")]
    for stress_case in malformed_response_cases():
        output, error = parse_and_validate(stress_case.raw_response, "CASE-777", retrieved)
        if stress_case.name == "markdown_fenced_json":
            assert output is not None
            assert error is None
        else:
            assert output is None
            assert isinstance(error, str)


def test_retriever_handles_low_overlap_query_with_empty_result():
    """Retriever should return empty list (not raise) for gibberish low-overlap input."""
    retriever = PolicyRetriever("policies.md")
    results = retriever.search("zzzxqv unseen token stream alpha omega")
    assert results == []


def test_escalation_checker_enforces_missing_field_guardrail():
    """EscalationChecker should force escalation when missing_fields are present."""
    case = _sample_case().model_copy(
        update={
            "attributes": _sample_case().attributes.model_copy(
                update={"missing_fields": ["identity_verified"]}
            )
        }
    )
    output = DecisionOutput(
        case_id="CASE-777",
        decision="APPROVE",
        confidence=0.88,
        policy_citations=[{"policy_id": "POL-001", "reason": "ok"}],
        audit_log={
            "retrieved_policies": ["POL-001"],
            "retrieval_score": 0.7,
            "timestamp": "2026-01-01T00:00:00Z",
            "retry_attempted": False,
        },
    )
    checked = EscalationChecker().check(
        output,
        case,
        [Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e")],
    )
    assert checked.decision == "ESCALATE"


def test_validate_with_retry_deterministic_fallback_on_repeated_failures(monkeypatch):
    """validate_with_retry should deterministically return fallback escalate after two failures."""
    monkeypatch.setattr(
        "validator.call_anthropic_api",
        lambda *args, **kwargs: '{"bad":"json"}',
    )
    output = validate_with_retry(
        raw_response="{broken",
        case_id="CASE-777",
        retrieved=[Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e")],
        agent=object(),
        case=_sample_case(),
    )
    assert output.decision == "ESCALATE"
    assert output.audit_log.retry_attempted is True
    assert "Attempt 1:" in (output.audit_log.error_detail or "")
    assert "Attempt 2:" in (output.audit_log.error_detail or "")
