"""
Output validation module. Parses raw LLM response, validates against Pydantic
schema, retries on failure, and applies escalation override rules.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from agent import SYSTEM_PROMPT, build_user_message, call_anthropic_api
from config import CONFIDENCE_THRESHOLD, ESCALATE_ON_MISSING_FIELDS, ESCALATE_ON_RETRIEVAL_FAILURE
from models import Case, DecisionOutput, Policy


CORRECTION_PROMPT_TEMPLATE = """
Your previous response was invalid. Here is why:

ERROR: {error_message}

YOUR INVALID RESPONSE:
{invalid_response}

You must return ONLY a valid JSON object matching this schema exactly:
{{
  "decision": "APPROVE" | "DENY" | "ESCALATE",
  "confidence": <float 0.0-1.0>,
  "policy_citations": [
    {{"policy_id": "<from provided policies only>", "reason": "<explanation>"}}
  ]
}}

Re-evaluate the case and respond now.

ORIGINAL CASE:
{original_user_message}
""".strip()


_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(raw_response: str) -> str:
    """Remove optional markdown code fences around LLM JSON output."""
    cleaned = _CODE_FENCE_RE.sub("", raw_response)
    return cleaned.strip()


def parse_and_validate(
    raw_response: str,
    case_id: str,
    retrieved: list[Policy],
) -> tuple[DecisionOutput | None, str | None]:
    """
    Parse raw LLM output and validate against DecisionOutput schema.

    Returns:
      - (DecisionOutput, None) on success
      - (None, error_message) on parse/validation failure
    This function never raises.
    """
    try:
        cleaned = _strip_code_fences(raw_response)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return None, f"JSON parse error: {exc}"

        retrieved_ids = [policy.policy_id for policy in retrieved]
        retrieval_score = max((policy.similarity_score for policy in retrieved), default=0.0)

        candidate = {
            "case_id": case_id,
            "decision": parsed.get("decision"),
            "confidence": parsed.get("confidence"),
            "policy_citations": parsed.get("policy_citations"),
            "audit_log": {
                "retrieved_policies": retrieved_ids,
                "retrieval_score": float(retrieval_score),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "retry_attempted": False,
                "error_detail": None,
            },
        }

        try:
            output = DecisionOutput(**candidate)
        except ValidationError as exc:
            return None, f"Validation error: {exc.errors()}"

        invalid_ids = [
            citation.policy_id
            for citation in output.policy_citations
            if citation.policy_id not in retrieved_ids
        ]
        if invalid_ids:
            filtered_citations = [
                citation
                for citation in output.policy_citations
                if citation.policy_id in retrieved_ids
            ]
            if not filtered_citations:
                return None, "All citations were invalid — no retrieved policy IDs were cited"

            error_detail = (
                "Removed non-retrieved policy citations: " + ", ".join(sorted(set(invalid_ids)))
            )
            output = output.model_copy(
                update={
                    "policy_citations": filtered_citations,
                    "audit_log": output.audit_log.model_copy(update={"error_detail": error_detail}),
                }
            )

        return output, None
    except Exception as exc:
        return None, f"Unexpected validation error: {exc}"


def validate_with_retry(
    raw_response: str,
    case_id: str,
    retrieved: list[Policy],
    agent: object,  # kept for signature compatibility in milestone contract
    case: Case,
) -> DecisionOutput:
    """
    Validate raw output, retry once with correction prompt, then escalate fallback.

    Returns DecisionOutput on every normal runtime path.
    """
    output, first_error = parse_and_validate(raw_response, case_id, retrieved)
    if output is not None:
        return output.model_copy(
            update={"audit_log": output.audit_log.model_copy(update={"retry_attempted": False})}
        )

    second_error = "Retry not attempted"
    try:
        original_user_message = build_user_message(case, retrieved)
        correction_prompt = CORRECTION_PROMPT_TEMPLATE.format(
            error_message=first_error or "Unknown validation failure",
            invalid_response=raw_response,
            original_user_message=original_user_message,
        )
        retry_response = call_anthropic_api(SYSTEM_PROMPT, correction_prompt)
        retry_output, retry_error = parse_and_validate(retry_response, case_id, retrieved)
        if retry_output is not None:
            return retry_output.model_copy(
                update={
                    "audit_log": retry_output.audit_log.model_copy(
                        update={"retry_attempted": True}
                    )
                }
            )
        second_error = retry_error or "Unknown retry validation failure"
    except Exception as exc:
        second_error = f"Retry call failed: {exc}"

    fallback_policy_id = retrieved[0].policy_id if retrieved else "POL-007"
    fallback_payload = {
        "case_id": case_id,
        "decision": "ESCALATE",
        "confidence": 0.0,
        "policy_citations": [
            {
                "policy_id": fallback_policy_id,
                "reason": "Automatic escalation: output validation failed after retry",
            }
        ],
        "audit_log": {
            "retrieved_policies": [policy.policy_id for policy in retrieved],
            "retrieval_score": float(
                max((policy.similarity_score for policy in retrieved), default=0.0)
            ),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "retry_attempted": True,
            "error_detail": (
                f"Attempt 1: {first_error or 'Unknown'} | Attempt 2: {second_error}"
            ),
        },
    }
    return DecisionOutput(**fallback_payload)


class EscalationChecker:
    """Apply deterministic post-validation escalation overrides."""

    def check(
        self,
        output: DecisionOutput,
        case: Case,
        retrieved: list[Policy],
    ) -> DecisionOutput:
        """Return possibly overridden DecisionOutput based on safety rules."""
        try:
            reasons: list[str] = []

            if output.confidence < CONFIDENCE_THRESHOLD:
                reasons.append(
                    f"Confidence {output.confidence:.2f} is below required threshold {CONFIDENCE_THRESHOLD}"
                )

            if ESCALATE_ON_MISSING_FIELDS and case.attributes.missing_fields:
                reasons.append(
                    "Case has missing critical fields: "
                    + ", ".join(case.attributes.missing_fields)
                )

            if ESCALATE_ON_RETRIEVAL_FAILURE and not retrieved:
                reasons.append("No policies were retrieved for this case")

            if case.attributes.identity_verified is True:
                verified_name = (case.attributes.verified_name or "").strip().lower()
                holder_name = (case.attributes.account_holder_name or "").strip().lower()
                if (
                    (verified_name and holder_name and verified_name != holder_name)
                    or verified_name == "unknown"
                    or holder_name == "unknown"
                ):
                    reasons.append("Conflicting identity signals detected in case attributes")

            if not reasons:
                return output

            if output.decision == "ESCALATE":
                if output.audit_log.error_detail is None:
                    return output.model_copy(
                        update={
                            "audit_log": output.audit_log.model_copy(
                                update={"error_detail": "Escalation reasons noted: " + "; ".join(reasons)}
                            )
                        }
                    )
                return output

            detail = "Escalation override applied. Reasons: " + "; ".join(reasons)
            return output.model_copy(
                update={
                    "decision": "ESCALATE",
                    "audit_log": output.audit_log.model_copy(update={"error_detail": detail}),
                }
            )
        except Exception:
            return output
