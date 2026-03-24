"""Stress harness helpers for robustness testing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StressCase:
    """Synthetic stress case specification."""

    name: str
    raw_response: str
    description: str


def malformed_response_cases() -> list[StressCase]:
    """Return representative malformed LLM response payloads."""
    return [
        StressCase(
            name="markdown_fenced_json",
            raw_response=(
                "```json\n"
                '{"decision":"APPROVE","confidence":0.8,'
                '"policy_citations":[{"policy_id":"POL-001","reason":"ok"}]}'
                "\n```"
            ),
            description="Response wrapped in markdown fences.",
        ),
        StressCase(
            name="non_json_text",
            raw_response="I think this should be approved because it looks safe.",
            description="Response that violates strict JSON contract.",
        ),
        StressCase(
            name="extra_fields_json",
            raw_response=(
                '{"decision":"APPROVE","confidence":0.8,'
                '"policy_citations":[{"policy_id":"POL-001","reason":"ok"}],'
                '"explanation":"extra field should fail"}'
            ),
            description="Response includes schema-forbidden field.",
        ),
    ]
