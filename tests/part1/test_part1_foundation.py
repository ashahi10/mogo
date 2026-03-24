"""Validation suite for Build Plan Part 1 (M1-M3)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

import config
from models import Case, DecisionOutput
from retriever import PolicyRetriever, build_retrieval_query, load_policies, validate_setup


ROOT = Path(__file__).resolve().parents[2]
POLICIES_PATH = ROOT / "policies.md"
CASES_PATH = ROOT / "cases.json"


def test_config_constants_match_part1_expectations() -> None:
    """Config constants should match M1 requirements."""
    assert config.MODEL_NAME == "claude-sonnet-4-5"
    assert config.MAX_TOKENS == 1024
    assert config.TEMPERATURE == 0.1
    assert config.RETRIEVAL_TOP_K == 3
    assert config.CONFIDENCE_THRESHOLD == 0.65
    assert config.MIN_POLICY_CITATIONS == 1
    assert config.CASES_FILE == "cases.json"
    assert config.POLICIES_FILE == "policies.md"
    assert config.ESCALATE_ON_MISSING_FIELDS is True
    assert config.ESCALATE_ON_RETRIEVAL_FAILURE is True
    assert config.ESCALATE_ON_VALIDATION_FAILURE is True


def test_decision_output_rejects_invalid_shapes() -> None:
    """DecisionOutput should reject empty citations, bad confidence, and extra fields."""
    base = {
        "case_id": "CASE-001",
        "decision": "APPROVE",
        "confidence": 0.8,
        "policy_citations": [{"policy_id": "POL-001", "reason": "Grounded in policy"}],
        "audit_log": {
            "retrieved_policies": ["POL-001"],
            "retrieval_score": 0.6,
            "timestamp": "2026-03-24T00:00:00Z",
            "retry_attempted": False,
        },
    }

    with pytest.raises(ValidationError):
        DecisionOutput(**{**base, "policy_citations": []})

    with pytest.raises(ValidationError):
        DecisionOutput(**{**base, "confidence": 1.3})

    with pytest.raises(ValidationError):
        DecisionOutput(**{**base, "explanation": "unexpected"})


def test_cases_dataset_distribution_and_schema_are_valid() -> None:
    """cases.json should have 14 valid cases with the required distribution."""
    raw_cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert len(raw_cases) == 14

    validated_cases = [Case(**item) for item in raw_cases]
    by_difficulty = Counter(case.difficulty for case in validated_cases)
    assert by_difficulty == {
        "straightforward": 8,
        "ambiguous": 4,
        "edge": 2,
    }

    straight_decisions = Counter(
        case.expected_decision for case in validated_cases if case.difficulty == "straightforward"
    )
    assert straight_decisions == {"APPROVE": 4, "DENY": 4}

    ambiguous_decisions = {
        case.expected_decision for case in validated_cases if case.difficulty == "ambiguous"
    }
    assert ambiguous_decisions == {"ESCALATE"}

    edge_decisions = {case.expected_decision for case in validated_cases if case.difficulty == "edge"}
    assert edge_decisions == {"ESCALATE"}


def test_policy_file_loads_exactly_seven_policies() -> None:
    """policies.md should parse into seven valid policy objects."""
    policies = load_policies(str(POLICIES_PATH))
    assert len(policies) == 7
    assert all(policy.similarity_score == 0.0 for policy in policies)
    assert {policy.policy_id for policy in policies} == {
        "POL-001",
        "POL-002",
        "POL-003",
        "POL-004",
        "POL-005",
        "POL-006",
        "POL-007",
    }


def test_retriever_end_to_end_from_case_to_search_results() -> None:
    """End-to-end retriever path should map representative cases to expected policies."""
    retriever = PolicyRetriever(str(POLICIES_PATH))
    all_cases = [Case(**item) for item in json.loads(CASES_PATH.read_text(encoding="utf-8"))]
    by_id = {case.case_id: case for case in all_cases}

    q_identity = build_retrieval_query(by_id["CASE-002"])
    result_identity = retriever.search(q_identity)
    assert result_identity
    assert result_identity[0].policy_id == "POL-001"

    q_risk = build_retrieval_query(by_id["CASE-005"])
    result_risk = retriever.search(q_risk)
    assert any(policy.policy_id == "POL-004" for policy in result_risk)

    q_missing = build_retrieval_query(by_id["CASE-013"])
    result_missing = retriever.search(q_missing)
    assert any(policy.policy_id == "POL-007" for policy in result_missing)

    no_match = retriever.search("xyzabc123 nonsense query with no matching terms")
    assert no_match == []


def test_validate_setup_success_and_failure_paths() -> None:
    """validate_setup should pass valid files and fail bad paths with RuntimeError."""
    validate_setup(str(POLICIES_PATH), str(CASES_PATH))

    with pytest.raises(RuntimeError):
        validate_setup(str(ROOT / "missing-policies.md"), str(CASES_PATH))
