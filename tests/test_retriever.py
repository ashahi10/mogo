"""Unit tests for retriever module behavior."""

from __future__ import annotations

from pathlib import Path

from models import Case, Policy
from retriever import PolicyRetriever, build_retrieval_query, load_policies


def test_load_policies_from_temporary_file(tmp_path):
    """load_policies should parse valid temporary policy markdown into Policy objects."""
    content = (
        "policy_id:\nPOL-101\ntitle:\nPolicy A\nrule:\nIf x then y.\n"
        "escalation_note:\nEscalate if unknown.\n---\n"
        "policy_id:\nPOL-102\ntitle:\nPolicy B\nrule:\nIf a then b.\n"
        "escalation_note:\nEscalate if unclear.\n---\n"
        "policy_id:\nPOL-103\ntitle:\nPolicy C\nrule:\nIf c then d.\n"
        "escalation_note:\nEscalate if missing.\n---\n"
        "policy_id:\nPOL-104\ntitle:\nPolicy D\nrule:\nIf d then e.\n"
        "escalation_note:\nEscalate if conflict.\n---\n"
        "policy_id:\nPOL-105\ntitle:\nPolicy E\nrule:\nIf e then f.\n"
        "escalation_note:\nEscalate if uncertain.\n---\n"
    )
    p = tmp_path / "policies.md"
    p.write_text(content, encoding="utf-8")

    policies = load_policies(str(p))
    assert len(policies) == 5
    assert isinstance(policies[0], Policy)
    assert all(policy.policy_id and policy.title and policy.rule for policy in policies)


def test_search_returns_identity_policy_as_top_result():
    """PolicyRetriever should rank POL-001 first for unverified identity query."""
    retriever = PolicyRetriever(str(Path("policies.md")))
    results = retriever.search("identity not verified payout denied")
    assert results
    assert results[0].policy_id == "POL-001"
    assert results[0].similarity_score > 0.0


def test_search_returns_empty_for_no_match_query():
    """PolicyRetriever should return empty list when query has no overlapping terms."""
    retriever = PolicyRetriever(str(Path("policies.md")))
    results = retriever.search("xyzabc completely unrelated gibberish terms")
    assert results == []


def test_build_retrieval_query_enriches_for_risk_and_mismatch():
    """build_retrieval_query should include high-risk and mismatch enrichment phrases."""
    case = Case(
        case_id="CASE-901",
        summary="Payout request with suspicious profile state.",
        attributes={
            "case_type": "payout_review",
            "payout_amount": 900.0,
            "identity_verified": True,
            "verified_name": "Jonathan Price",
            "account_holder_name": "J. Price",
            "recent_profile_changes": 2,
            "high_risk_flag": True,
            "account_age_days": 120,
            "missing_fields": [],
            "transaction_velocity": 2,
        },
        expected_decision="ESCALATE",
        difficulty="ambiguous",
    )
    query = build_retrieval_query(case)
    assert "high risk" in query
    assert "name mismatch" in query
