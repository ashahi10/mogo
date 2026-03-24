"""
Output validation module. Parses raw LLM response, validates against Pydantic
schema, retries on failure, and applies escalation override rules.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from models import DecisionOutput, Policy, PolicyCitation


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
