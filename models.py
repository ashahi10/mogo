"""Pydantic v2 data contracts for Orion AI Decision Agent."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import MIN_POLICY_CITATIONS

CASE_ID_PATTERN = re.compile(r"^CASE-\d{3}$")
POLICY_ID_PATTERN = re.compile(r"^POL-\d{3}$")
SCRIPT_TAG_PATTERN = re.compile(r"<script.*?>.*?</script>", flags=re.IGNORECASE | re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class CaseAttributes(BaseModel):
    """Structured attributes attached to a compliance case."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    case_type: str
    payout_amount: Optional[float] = None
    identity_verified: Optional[bool] = None
    verified_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    recent_profile_changes: Optional[int] = None
    high_risk_flag: Optional[bool] = None
    account_age_days: Optional[int] = None
    missing_fields: list[str] = Field(default_factory=list)
    transaction_velocity: Optional[int] = None
    device_trust_score: Optional[float] = None
    geolocation_mismatch: Optional[bool] = None
    impossible_travel_flag: Optional[bool] = None
    recent_password_reset_hours: Optional[int] = None
    payout_destination_recently_changed: Optional[bool] = None
    kyc_age_days: Optional[int] = None
    kyc_confidence: Optional[float] = None
    sanctions_watchlist_hit: Optional[bool] = None
    historical_avg_payout: Optional[float] = None
    historical_payout_stddev: Optional[float] = None
    data_conflict_flag: Optional[bool] = None

    @field_validator("payout_amount")
    @classmethod
    def payout_amount_non_negative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("payout_amount must be non-negative")
        return value

    @field_validator("account_age_days")
    @classmethod
    def account_age_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("account_age_days must be non-negative")
        return value

    @field_validator("recent_profile_changes")
    @classmethod
    def profile_changes_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("recent_profile_changes must be non-negative")
        return value

    @field_validator("device_trust_score", "kyc_confidence")
    @classmethod
    def probability_fields_in_range(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError("probability-like fields must be between 0.0 and 1.0")
        return value

    @field_validator(
        "recent_password_reset_hours",
        "kyc_age_days",
    )
    @classmethod
    def non_negative_integer_fields(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("integer risk metadata fields must be non-negative")
        return value

    @field_validator("historical_avg_payout", "historical_payout_stddev")
    @classmethod
    def non_negative_float_fields(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("historical payout fields must be non-negative")
        return value


class Case(BaseModel):
    """Top-level case model used as pipeline input."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    case_id: str
    summary: str
    attributes: CaseAttributes
    expected_decision: Literal["APPROVE", "DENY", "ESCALATE"]
    difficulty: Literal["straightforward", "ambiguous", "edge"]
    scenario_type: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("case_id")
    @classmethod
    def case_id_format(cls, value: str) -> str:
        if not CASE_ID_PATTERN.match(value):
            raise ValueError("case_id must match CASE-XXX")
        return value

    @field_validator("summary")
    @classmethod
    def sanitize_summary(cls, value: str) -> str:
        cleaned = SCRIPT_TAG_PATTERN.sub("", value)
        cleaned = HTML_TAG_PATTERN.sub("", cleaned)
        cleaned = cleaned.strip()
        return cleaned[:1000]


class Policy(BaseModel):
    """Policy rule model loaded from policies.md."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    policy_id: str
    title: str
    rule: str
    escalation_note: Optional[str] = None
    similarity_score: float = 0.0

    @field_validator("policy_id")
    @classmethod
    def policy_id_format(cls, value: str) -> str:
        if not POLICY_ID_PATTERN.match(value):
            raise ValueError("policy_id must match POL-XXX")
        return value

    @field_validator("similarity_score")
    @classmethod
    def similarity_score_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("similarity_score must be between 0.0 and 1.0")
        return value


class PolicyCitation(BaseModel):
    """Model citation linking a decision to a retrieved policy."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    policy_id: str
    reason: str

    @field_validator("policy_id")
    @classmethod
    def citation_policy_id_format(cls, value: str) -> str:
        if not POLICY_ID_PATTERN.match(value):
            raise ValueError("policy_id must match POL-XXX")
        return value

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Citation reason must not be empty")
        return value


class AuditLog(BaseModel):
    """Audit metadata generated for every decision output."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    retrieved_policies: list[str]
    retrieval_score: float
    timestamp: str
    retry_attempted: bool
    error_detail: Optional[str] = None

    @field_validator("retrieval_score")
    @classmethod
    def retrieval_score_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("retrieval_score must be between 0.0 and 1.0")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("timestamp must be a non-empty string")
        return value


class DecisionOutput(BaseModel):
    """Final validated decision output returned by the pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    case_id: str
    decision: Literal["APPROVE", "DENY", "ESCALATE"]
    confidence: float
    policy_citations: list[PolicyCitation]
    audit_log: AuditLog

    @field_validator("case_id")
    @classmethod
    def output_case_id_format(cls, value: str) -> str:
        if not CASE_ID_PATTERN.match(value):
            raise ValueError("case_id must match CASE-XXX")
        return value

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Confidence must be 0.0–1.0, got {value}")
        return value

    @field_validator("policy_citations")
    @classmethod
    def must_have_citations(cls, value: list[PolicyCitation]) -> list[PolicyCitation]:
        if len(value) < MIN_POLICY_CITATIONS:
            raise ValueError(
                f"At least {MIN_POLICY_CITATIONS} policy citation(s) are required"
            )
        return value
