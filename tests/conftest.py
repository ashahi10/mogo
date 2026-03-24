"""Shared pytest fixtures for Orion decision agent tests."""

from __future__ import annotations

import pytest

from models import Case, Policy


VALID_DECISION_JSON = (
    '{"decision":"APPROVE","confidence":0.9,'
    '"policy_citations":[{"policy_id":"POL-001","reason":"Policy grounded decision"}]}'
)


@pytest.fixture
def sample_case() -> Case:
    """Return a valid sample case object used across unit tests."""
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


@pytest.fixture
def sample_retrieved() -> list[Policy]:
    """Return a single retrieved policy fixture used for validation tests."""
    return [
        Policy(
            policy_id="POL-001",
            title="Identity Verification Required",
            rule="If identity_verified is false, then deny the payout request.",
            escalation_note="Escalate if status is unknown.",
            similarity_score=0.8,
        )
    ]
