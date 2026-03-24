"""Unit tests for decision agent behavior."""

import json

import agent
from models import Case, Policy


def _sample_case() -> Case:
    return Case(
        case_id="CASE-001",
        summary="Sample payout case",
        attributes={
            "case_type": "payout_review",
            "payout_amount": 300.0,
            "identity_verified": True,
            "verified_name": "Ari Shah",
            "account_holder_name": "Ari Shah",
            "recent_profile_changes": 0,
            "high_risk_flag": False,
            "account_age_days": 120,
            "missing_fields": [],
            "transaction_velocity": 1,
        },
        expected_decision="APPROVE",
        difficulty="straightforward",
    )


def test_decide_escalates_when_retriever_returns_empty_list(monkeypatch):
    """Agent should escalate and skip API call on empty retrieval."""
    called = {"api": 0}

    class EmptyRetriever:
        def search(self, query):
            return []

    def fake_api(*args, **kwargs):
        called["api"] += 1
        return "{}"

    monkeypatch.setattr(agent, "call_anthropic_api", fake_api)
    decision_agent = agent.DecisionAgent(EmptyRetriever())
    raw, retrieved = decision_agent.decide(_sample_case())

    parsed = json.loads(raw)
    assert parsed["decision"] == "ESCALATE"
    assert retrieved == []
    assert called["api"] == 0


def test_decide_escalates_when_api_raises(monkeypatch):
    """Agent should return ESCALATE JSON when API call fails."""

    class OneRetriever:
        def search(self, query):
            return [Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e")]

    def fake_api(*args, **kwargs):
        raise Exception("connection failed")

    monkeypatch.setattr(agent, "call_anthropic_api", fake_api)
    decision_agent = agent.DecisionAgent(OneRetriever())
    raw, _ = decision_agent.decide(_sample_case())

    parsed = json.loads(raw)
    assert parsed["decision"] == "ESCALATE"


def test_decide_returns_raw_response_on_success(monkeypatch):
    """Agent should return API raw JSON and retrieved policies on success."""
    expected_raw = (
        '{"decision":"APPROVE","confidence":0.9,'
        '"policy_citations":[{"policy_id":"POL-001","reason":"ok"}]}'
    )

    class OneRetriever:
        def search(self, query):
            return [Policy(policy_id="POL-001", title="t", rule="r", escalation_note="e")]

    monkeypatch.setattr(agent, "call_anthropic_api", lambda *args, **kwargs: expected_raw)
    decision_agent = agent.DecisionAgent(OneRetriever())
    raw, retrieved = decision_agent.decide(_sample_case())

    assert raw == expected_raw
    assert isinstance(retrieved, list)
    assert retrieved
