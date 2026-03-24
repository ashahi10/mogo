"""
Decision agent module. Orchestrates retrieval, prompt construction, and
Claude API call to produce structured compliance decisions per case.
"""

from __future__ import annotations

from models import Case, Policy


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
