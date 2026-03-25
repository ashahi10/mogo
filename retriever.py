"""
Policy retrieval module. Loads policies from markdown, builds TF-IDF index,
and exposes search_policies() for similarity-based policy lookup.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import CASES_FILE, POLICIES_FILE, RETRIEVAL_TOP_K
from models import Case, Policy


FIELD_LABEL_RE = re.compile(r"(?im)^(policy_id|title|rule|escalation_note):\s*$")


def _extract_policy_fields(block: str) -> dict[str, str]:
    """Extract labeled policy fields from a markdown policy block."""
    matches = list(FIELD_LABEL_RE.finditer(block))
    if not matches:
        return {}

    extracted: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1).lower()
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
        value = block[value_start:value_end].strip()
        extracted[label] = value
    return extracted


def load_policies(path: str) -> list[Policy]:
    """
    Load policy blocks from markdown and return validated Policy model instances.

    Policy blocks are separated with a markdown delimiter line of `---`.
    """
    policy_path = Path(path)
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found at expected path: {path}")

    raw = policy_path.read_text(encoding="utf-8")
    blocks = [block.strip() for block in raw.split("\n---\n") if block.strip()]
    if len(blocks) < 5:
        raise ValueError(
            f"Expected at least 5 policy blocks in {path}, found {len(blocks)}"
        )

    policies: list[Policy] = []
    for block_index, block in enumerate(blocks, start=1):
        fields = _extract_policy_fields(block)
        try:
            policy = Policy(
                policy_id=fields["policy_id"],
                title=fields["title"],
                rule=fields["rule"],
                escalation_note=fields.get("escalation_note") or None,
                similarity_score=0.0,
            )
            policies.append(policy)
        except KeyError as exc:
            missing_key = exc.args[0]
            raise ValueError(
                f"Policy block {block_index} is missing required field '{missing_key}'"
            ) from exc
        except Exception as exc:  # Pydantic validation and shape errors
            raise ValueError(f"Policy block {block_index} failed validation: {exc}") from exc

    return policies


class PolicyRetriever:
    """TF-IDF retriever that returns top-k relevant policies for a query."""

    def __init__(self, policies_path: str):
        self.policies: list[Policy] = load_policies(policies_path)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=500,
        )
        corpus = [
            f"{policy.title} {policy.rule} {policy.escalation_note or ''}"
            for policy in self.policies
        ]
        self.policy_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> list[Policy]:
        """
        Return top-k policies sorted by descending cosine similarity.

        On runtime retrieval failure, return an empty list rather than raising.
        """
        try:
            query_vec = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self.policy_matrix)[0]
            top_indices = scores.argsort()[::-1][:top_k]

            results: list[Policy] = []
            for idx in top_indices:
                score = float(scores[idx])
                if score <= 0.0:
                    continue
                policy_copy = self.policies[idx].model_copy()
                policy_copy.similarity_score = round(score, 4)
                results.append(policy_copy)
            return results
        except Exception as exc:  # Defensive safety net for retrieval runtime failures.
            print(f"Retriever search error: {exc}", file=sys.stderr)
            return []


def build_retrieval_query(case: Case) -> str:
    """
    Build an enriched retrieval query from case summary + structured attributes.

    Enrichment improves lexical overlap with policy text for TF-IDF retrieval.
    """
    parts: list[str] = [case.summary]
    attrs = case.attributes

    if attrs.high_risk_flag is True:
        parts.append("high risk flagged account")

    if attrs.missing_fields:
        parts.append(f"missing fields: {', '.join(attrs.missing_fields)}")

    if attrs.identity_verified is False:
        parts.append("identity not verified unverified account")

    if attrs.identity_verified is None:
        parts.append("identity verification status unknown missing")

    verified_name = (attrs.verified_name or "").strip().lower()
    holder_name = (attrs.account_holder_name or "").strip().lower()
    if verified_name and holder_name and verified_name != holder_name:
        parts.append("name mismatch identity discrepancy account holder mismatch")

    if attrs.recent_profile_changes is not None and attrs.recent_profile_changes >= 2:
        parts.append("multiple recent profile changes velocity suspicious activity")

    if attrs.payout_amount is not None and attrs.payout_amount > 5000:
        parts.append("large payout high value transaction threshold")

    if attrs.account_age_days is not None and attrs.account_age_days < 60:
        parts.append("new account age restriction recently opened")

    if attrs.impossible_travel_flag is True:
        parts.append("impossible travel geolocation anomaly")

    if attrs.geolocation_mismatch is True:
        parts.append("geolocation mismatch unusual location")

    if attrs.device_trust_score is not None and attrs.device_trust_score < 0.4:
        parts.append("low device trust unfamiliar device")

    if (
        attrs.recent_password_reset_hours is not None
        and attrs.recent_password_reset_hours <= 24
    ):
        parts.append("recent password reset account security event")

    if attrs.payout_destination_recently_changed is True:
        parts.append("recent payout destination change beneficiary update")

    if attrs.kyc_age_days is not None and attrs.kyc_age_days > 365:
        parts.append("stale kyc profile reverification required")

    if attrs.kyc_confidence is not None and attrs.kyc_confidence < 0.6:
        parts.append("low confidence kyc verification")

    if attrs.sanctions_watchlist_hit is True:
        parts.append("watchlist hit sanctions screening escalation")

    if attrs.data_conflict_flag is True:
        parts.append("conflicting data source disagreement")

    if (
        attrs.historical_avg_payout is not None
        and attrs.payout_amount is not None
        and attrs.historical_avg_payout > 0
        and attrs.payout_amount > attrs.historical_avg_payout * 3
    ):
        parts.append("payout pattern drift amount anomaly")

    session_level_hits = sum([
        attrs.impossible_travel_flag is True,
        attrs.geolocation_mismatch is True,
        attrs.device_trust_score is not None and attrs.device_trust_score < 0.4,
        attrs.recent_password_reset_hours is not None
        and attrs.recent_password_reset_hours <= 24,
    ])
    if session_level_hits >= 2:
        parts.append(
            "composite security event POL-019 concurrent session anomalies "
            "escalate manual review precedence over single-signal deny"
        )

    return " ".join(parts)


def validate_setup(policies_path: str, cases_path: str) -> None:
    """Validate core dataset setup before running retrieval-dependent flows."""
    try:
        policies = load_policies(policies_path)
        if len(policies) < 5:
            raise RuntimeError(
                f"Setup validation failed: expected at least 5 policies, found {len(policies)}."
            )
    except Exception as exc:
        raise RuntimeError(
            f"Setup validation failed while loading policies from '{policies_path}': {exc}"
        ) from exc

    try:
        with open(cases_path, "r", encoding="utf-8") as handle:
            cases_data = json.load(handle)
    except Exception as exc:
        raise RuntimeError(
            f"Setup validation failed while reading cases from '{cases_path}': {exc}"
        ) from exc

    if not isinstance(cases_data, list):
        raise RuntimeError(
            f"Setup validation failed: expected JSON array in '{cases_path}'."
        )
    if len(cases_data) < 10:
        raise RuntimeError(
            f"Setup validation failed: expected at least 10 cases, found {len(cases_data)}."
        )

    print(
        f"Setup validated: {len(policies)} policies, {len(cases_data)} cases loaded.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    validate_setup(POLICIES_FILE, CASES_FILE)
