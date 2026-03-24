"""
Batch evaluation module. Runs all cases through the pipeline, computes
metrics, and prints the formatted evaluation report.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import time

from agent import DecisionAgent
from config import CASES_FILE, POLICIES_FILE
from models import Case
from retriever import PolicyRetriever
from validator import run_pipeline


@dataclass
class EvalResult:
    """Single-case evaluation result row."""

    case_id: str
    difficulty: str
    expected: str
    got: str
    confidence: float
    retry_attempted: bool


@dataclass
class Metrics:
    """Aggregate evaluation metrics for the full run."""

    total: int
    accuracy: float
    approve_count: int
    deny_count: int
    escalate_count: int
    ambiguous_escalated_pct: float
    straight_not_escalated_pct: float
    edge_escalated_pct: float
    ambiguous_escalated_count: int
    ambiguous_total: int
    straight_not_escalated_count: int
    straight_total: int
    edge_escalated_count: int
    edge_total: int


def compute_metrics(results: list[EvalResult]) -> Metrics:
    """Compute project-required aggregate metrics from per-case results."""
    total = len(results)
    correct = sum(1 for row in results if row.got == row.expected)

    straightforward = [row for row in results if row.difficulty == "straightforward"]
    ambiguous = [row for row in results if row.difficulty == "ambiguous"]
    edge = [row for row in results if row.difficulty == "edge"]

    ambiguous_escalated_count = sum(1 for row in ambiguous if row.got == "ESCALATE")
    straight_not_escalated_count = sum(1 for row in straightforward if row.got != "ESCALATE")
    edge_escalated_count = sum(1 for row in edge if row.got == "ESCALATE")

    return Metrics(
        total=total,
        accuracy=(correct / total) if total else 0.0,
        approve_count=sum(1 for row in results if row.got == "APPROVE"),
        deny_count=sum(1 for row in results if row.got == "DENY"),
        escalate_count=sum(1 for row in results if row.got == "ESCALATE"),
        ambiguous_escalated_pct=(
            ambiguous_escalated_count / len(ambiguous) if ambiguous else 0.0
        ),
        straight_not_escalated_pct=(
            straight_not_escalated_count / len(straightforward) if straightforward else 0.0
        ),
        edge_escalated_pct=(edge_escalated_count / len(edge) if edge else 0.0),
        ambiguous_escalated_count=ambiguous_escalated_count,
        ambiguous_total=len(ambiguous),
        straight_not_escalated_count=straight_not_escalated_count,
        straight_total=len(straightforward),
        edge_escalated_count=edge_escalated_count,
        edge_total=len(edge),
    )


def _print_report(results: list[EvalResult], metrics: Metrics, runtime_s: float) -> None:
    """Render evaluation report in required human-readable format."""
    correct = sum(1 for row in results if row.got == row.expected)

    straight_pass = metrics.straight_not_escalated_pct >= 0.85
    ambiguous_pass = metrics.ambiguous_escalated_pct >= 0.75
    edge_pass = metrics.edge_escalated_pct >= 1.0

    print("============================================================")
    print("  ORION DECISION AGENT — EVALUATION REPORT")
    print("============================================================")
    print()
    print(f"Total cases run : {metrics.total}")
    print(f"Approve         : {metrics.approve_count}")
    print(f"Deny            : {metrics.deny_count}")
    print(f"Escalate        : {metrics.escalate_count}")
    print()
    print(
        "Overall accuracy (vs labels) : "
        f"{metrics.accuracy * 100:.1f}%  ({correct}/{metrics.total})"
    )
    print()
    print("By difficulty tier:")
    print(
        "  Straightforward "
        f"({metrics.straight_total}) — NOT escalated : "
        f"{metrics.straight_not_escalated_pct * 100:.1f}%  "
        f"({metrics.straight_not_escalated_count}/{metrics.straight_total})    "
        f"{'✓' if straight_pass else '✗'} target ≥ 85%"
    )
    print(
        "  Ambiguous       "
        f"({metrics.ambiguous_total}) — Escalated     : "
        f"{metrics.ambiguous_escalated_pct * 100:.1f}% "
        f"({metrics.ambiguous_escalated_count}/{metrics.ambiguous_total})    "
        f"{'✓' if ambiguous_pass else '✗'} target ≥ 75%"
    )
    print(
        "  Edge cases      "
        f"({metrics.edge_total}) — Escalated     : "
        f"{metrics.edge_escalated_pct * 100:.1f}% "
        f"({metrics.edge_escalated_count}/{metrics.edge_total})    "
        f"{'✓' if edge_pass else '✗'} target 100%"
    )
    print()
    print("------------------------------------------------------------")
    print("  Per-case breakdown")
    print("------------------------------------------------------------")
    for row in results:
        status = "PASS ✓" if row.got == row.expected else "FAIL ✗"
        print(
            f"  {row.case_id} | {row.difficulty:<15} | "
            f"Expected: {row.expected:<9} | Got: {row.got:<9} | {status}"
        )
    print("============================================================")
    print(f"Runtime: {runtime_s:.2f}s")


if __name__ == "__main__":
    start = time.time()
    results: list[EvalResult] = []

    with open(CASES_FILE, "r", encoding="utf-8") as handle:
        raw_cases = json.load(handle)
    cases = [Case(**item) for item in raw_cases]

    retriever = PolicyRetriever(POLICIES_FILE)
    agent = DecisionAgent(retriever)

    for index, case in enumerate(cases, start=1):
        print(f"Processing {case.case_id} ({index}/{len(cases)})...", file=sys.stderr)
        try:
            decision = run_pipeline(case, agent)
            got = decision.decision
            confidence = decision.confidence
            retry_attempted = decision.audit_log.retry_attempted
        except Exception as exc:
            print(f"Error while processing {case.case_id}: {exc}", file=sys.stderr)
            got = "ESCALATE"
            confidence = 0.0
            retry_attempted = True

        results.append(
            EvalResult(
                case_id=case.case_id,
                difficulty=case.difficulty,
                expected=case.expected_decision,
                got=got,
                confidence=confidence,
                retry_attempted=retry_attempted,
            )
        )

    metrics = compute_metrics(results)
    runtime_s = time.time() - start
    _print_report(results, metrics, runtime_s)

    sys.exit(0 if metrics.accuracy >= 0.70 else 1)
