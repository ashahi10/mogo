"""
Policy retrieval module. Loads policies from markdown, builds TF-IDF index,
and exposes search_policies() for similarity-based policy lookup.
"""

from __future__ import annotations

import sys
from pathlib import Path
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import RETRIEVAL_TOP_K
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
