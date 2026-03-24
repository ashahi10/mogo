"""
Policy retrieval module. Loads policies from markdown, builds TF-IDF index,
and exposes search_policies() for similarity-based policy lookup.
"""

from __future__ import annotations

from pathlib import Path
import re

from models import Policy


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
