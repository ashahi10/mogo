"""Unit tests for validator parsing, retry, and escalation logic."""

from pathlib import Path
import json
from types import SimpleNamespace

import validator
from models import Case, DecisionOutput, Policy


def _sample_case(case_id: str = "CASE-001") -> Case:
    cases = json.loads(Path("cases.json").read_text(encoding="utf-8"))
    return Case(**next(c for c in cases if c["case_id"] == case_id))


def _retrieved() -> list[Policy]:
    return [Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e", similarity_score=0.8)]


def test_parse_and_validate_succeeds_on_valid_json():
    """parse_and_validate should return DecisionOutput and no error for valid payload."""
    raw = (
        '{"decision":"APPROVE","confidence":0.9,'
        '"policy_citations":[{"policy_id":"POL-001","reason":"grounded"}]}'
    )
    output, error = validator.parse_and_validate(raw, "CASE-001", _retrieved())
    assert output is not None
    assert error is None


def test_parse_and_validate_fails_on_invalid_json():
    """parse_and_validate should report JSON parse error and return no output."""
    output, error = validator.parse_and_validate('{"broken json', "CASE-001", [])
    assert output is None
    assert isinstance(error, str)
    assert "JSON" in error


def test_escalation_checker_overrides_low_confidence():
    """EscalationChecker should override non-escalate decision when confidence is below threshold."""
    output = DecisionOutput(
        case_id="CASE-001",
        decision="APPROVE",
        confidence=0.40,
        policy_citations=[{"policy_id": "POL-001", "reason": "ok"}],
        audit_log={
            "retrieved_policies": ["POL-001"],
            "retrieval_score": 0.7,
            "timestamp": "2026-01-01T00:00:00Z",
            "retry_attempted": False,
        },
    )
    checked = validator.EscalationChecker().check(output, _sample_case(), _retrieved())
    assert checked.decision == "ESCALATE"
    assert checked.audit_log.error_detail is not None


def test_validate_with_retry_escalates_after_two_failures(monkeypatch):
    """validate_with_retry should return fallback ESCALATE output when both attempts fail."""
    stub_agent = SimpleNamespace(
        invoke_model=lambda _sp, _um: '{"bad":"json"}',
    )
    output = validator.validate_with_retry(
        '{"broken json', "CASE-001", _retrieved(), stub_agent, _sample_case()
    )
    assert output.decision == "ESCALATE"
    assert output.audit_log.retry_attempted is True


def test_case_011_clear_mismatch_deny_is_not_forced_to_escalate():
    """EscalationChecker should not auto-escalate a clear mismatch deny case from policy POL-002."""
    case_011 = _sample_case("CASE-011")
    output = DecisionOutput(
        case_id="CASE-011",
        decision="DENY",
        confidence=0.92,
        policy_citations=[{"policy_id": "POL-002", "reason": "clear mismatch above threshold"}],
        audit_log={
            "retrieved_policies": ["POL-002"],
            "retrieval_score": 0.81,
            "timestamp": "2026-01-01T00:00:00Z",
            "retry_attempted": False,
        },
    )
    retrieved = [Policy(policy_id="POL-002", title="t", rule="r", escalation_note="e", similarity_score=0.81)]
    checked = validator.EscalationChecker().check(output, case_011, retrieved)
    assert checked.decision == "DENY"
