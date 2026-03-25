"""
Decision agent module. Orchestrates retrieval, prompt construction, and
Claude API call to produce structured compliance decisions per case.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    CASES_FILE,
    MAX_TOKENS,
    MODEL_NAME,
    POLICIES_FILE,
    TEMPERATURE,
)
from models import Case, Policy
from retriever import PolicyRetriever, build_retrieval_query


SYSTEM_PROMPT = """
You are a compliance decision agent in a regulated fintech environment.

Decide using ONLY the policies provided in the user message. Do not use outside knowledge.

Decision options:
- APPROVE: the case clearly satisfies policy requirements with no material risk signal.
- DENY: the case clearly violates one or more policies.
- ESCALATE: uncertainty, conflicting signals, missing/contradictory data, or partial policy fit.

Escalate when:
- confidence is below 0.65
- important fields are missing or contradictory
- policy signals conflict
- decision cannot be grounded in provided policies

Return ONLY valid JSON in this exact schema:
{
  "decision": "APPROVE" | "DENY" | "ESCALATE",
  "confidence": <float 0.0-1.0>,
  "policy_citations": [
    {
      "policy_id": "<must be from provided policies only>",
      "reason": "<specific policy-grounded justification>"
    }
  ]
}

Requirements:
- Cite only policy IDs from the provided policies.
- Include at least one citation.
- Return only the JSON object, with no prose, no markdown, and no trailing text.
""".strip()


def _format_attribute_label(key: str) -> str:
    """Convert snake_case keys into human-readable title case labels."""
    return key.replace("_", " ").title()


def _format_attribute_value(key: str, value: object) -> str:
    """Render values consistently for prompt readability."""
    if key == "missing_fields":
        if isinstance(value, list):
            return ", ".join(value) if value else "none"
        return "none"
    if value is None:
        return "not provided"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def build_user_message(case: Case, retrieved_policies: list[Policy]) -> str:
    """Build the user message containing case context and retrieved policies."""
    attrs = case.attributes.model_dump()

    attribute_lines: list[str] = []
    for key, value in attrs.items():
        label = _format_attribute_label(key)
        rendered = _format_attribute_value(key, value)
        attribute_lines.append(f"- {label}: {rendered}")

    missing_fields = attrs.get("missing_fields", [])
    if missing_fields:
        attribute_lines.append(f"- Missing Data: {', '.join(missing_fields)}")

    if retrieved_policies:
        policy_lines: list[str] = []
        for policy in retrieved_policies:
            policy_lines.append(
                "\n".join(
                    [
                        f"{policy.policy_id} - {policy.title}",
                        f"Rule: {policy.rule}",
                        f"Escalation Note: {policy.escalation_note or 'not provided'}",
                    ]
                )
            )
        policies_section = "\n\n".join(policy_lines)
    else:
        policies_section = (
            "No policies were retrieved for this case. "
            "If no grounded decision is possible, return ESCALATE."
        )

    return "\n".join(
        [
            f"CASE: {case.case_id}",
            "",
            "SUMMARY:",
            case.summary,
            "",
            "CASE ATTRIBUTES:",
            *attribute_lines,
            "",
            "RELEVANT POLICIES:",
            policies_section,
            "",
            "Issue your decision now.",
        ]
    )


def call_anthropic_api(system_prompt: str, user_message: str) -> str:
    """
    Execute a single Anthropic Messages API call and return raw text content.

    Retry policy:
    - Retry exactly once after 1 second only for RateLimitError.
    - All other Anthropic errors are raised immediately.
    """
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL or None,
    )

    def _invoke() -> str:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        if not response.content:
            raise ValueError("Anthropic response contained no content blocks.")
        return response.content[0].text

    try:
        return _invoke()
    except anthropic.RateLimitError:
        time.sleep(1)
        return _invoke()
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(
            "Anthropic authentication failed. "
            "Check ANTHROPIC_API_KEY in your environment/.env."
        ) from exc
    except anthropic.APIConnectionError:
        raise
    except anthropic.APIError:
        raise


class DecisionAgent:
    """Single-case decision orchestrator for retrieval + LLM decisioning."""

    def __init__(self, retriever: PolicyRetriever):
        self.retriever = retriever

    def invoke_model(self, system_prompt: str, user_message: str) -> str:
        """
        Single entry point for Anthropic completion calls from this agent.

        Used by the primary decision path and by the validator retry path so
        rate-limit and error behavior stay centralized in call_anthropic_api.
        """
        return call_anthropic_api(system_prompt, user_message)

    def decide(self, case: Case) -> tuple[str, list[Policy]]:
        """
        Return raw decision JSON text and retrieved policies.

        The method never raises; errors are converted to safe escalation JSON.
        """
        retrieved: list[Policy] = []
        try:
            query = build_retrieval_query(case)
            retrieved = self.retriever.search(query)

            if not retrieved:
                return (
                    self._build_escalation_response(
                        case_id=case.case_id,
                        reason="Policy retrieval returned no results",
                        retrieved=[],
                    ),
                    [],
                )

            user_message = build_user_message(case, retrieved)
            raw_response = self.invoke_model(SYSTEM_PROMPT, user_message)
            return raw_response, retrieved
        except Exception as exc:
            return (
                self._build_escalation_response(
                    case_id=case.case_id,
                    reason=f"Decision pipeline error: {exc}",
                    retrieved=retrieved,
                ),
                retrieved,
            )

    def _build_escalation_response(
        self,
        case_id: str,
        reason: str,
        retrieved: list[Policy],
    ) -> str:
        """Build guaranteed-parseable ESCALATE fallback JSON string."""
        fallback_policy_id = retrieved[0].policy_id if retrieved else "POL-007"
        payload = {
            "decision": "ESCALATE",
            "confidence": 0.0,
            "policy_citations": [
                {
                    "policy_id": fallback_policy_id,
                    "reason": reason,
                }
            ],
        }
        return json.dumps(payload)


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print(
            "Missing ANTHROPIC_API_KEY. "
            "Set it in your environment or .env before running agent smoke test."
        )
        sys.exit(1)

    try:
        cases_path = Path(CASES_FILE)
        cases_data = json.loads(cases_path.read_text(encoding="utf-8"))
        if not cases_data:
            print("No cases found in cases.json; smoke test requires at least one case.")
            sys.exit(1)

        # This smoke path intentionally performs one real API call.
        sample_case = Case(**cases_data[0])
        retriever = PolicyRetriever(POLICIES_FILE)
        decision_agent = DecisionAgent(retriever)
        raw_response, retrieved_policies = decision_agent.decide(sample_case)

        retrieved_ids = ", ".join(policy.policy_id for policy in retrieved_policies) or "none"
        print(f"Case ID: {sample_case.case_id}")
        print(f"Retrieved Policies: {retrieved_ids}")
        print(f"Raw Response: {raw_response}")
    except Exception as exc:
        print(f"Smoke test failed: {exc}")
        sys.exit(1)
