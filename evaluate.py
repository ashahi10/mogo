"""
Batch evaluation module. Runs all cases through the pipeline, computes
metrics, and prints the formatted evaluation report.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import sys
import time

from agent import DecisionAgent
from config import CASES_FILE, POLICIES_FILE
from models import Case, DecisionOutput
from retriever import PolicyRetriever
from validator import (
    compute_guardrail_indicators,
    confidence_calibration_snapshot,
    run_pipeline,
)


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
    retry_attempted_count: int
    avg_confidence: float
    straight_accuracy: float = 0.0
    ambiguous_accuracy: float = 0.0
    edge_accuracy: float = 0.0
    straight_correct: int = 0
    ambiguous_correct: int = 0
    edge_correct: int = 0


MODE_FILE_MAP = {
    "baseline": {
        "cases_file": CASES_FILE,
        "policies_file": POLICIES_FILE,
    },
    "extended": {
        "cases_file": "cases_extended.json",
        "policies_file": "policies_extended.md",
    },
}


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
    retry_attempted_count = sum(1 for row in results if row.retry_attempted)
    avg_confidence = (
        sum(row.confidence for row in results) / total if total else 0.0
    )

    straight_correct = sum(1 for row in straightforward if row.got == row.expected)
    ambiguous_correct = sum(1 for row in ambiguous if row.got == row.expected)
    edge_correct = sum(1 for row in edge if row.got == row.expected)

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
        retry_attempted_count=retry_attempted_count,
        avg_confidence=avg_confidence,
        straight_accuracy=(straight_correct / len(straightforward)) if straightforward else 0.0,
        ambiguous_accuracy=(ambiguous_correct / len(ambiguous)) if ambiguous else 0.0,
        edge_accuracy=(edge_correct / len(edge)) if edge else 0.0,
        straight_correct=straight_correct,
        ambiguous_correct=ambiguous_correct,
        edge_correct=edge_correct,
    )


def _print_report(
    results: list[EvalResult], metrics: Metrics, runtime_s: float, mode: str = "baseline"
) -> None:
    """Render evaluation report in required human-readable format."""
    correct = sum(1 for row in results if row.got == row.expected)
    use_baseline_tier_metrics = (mode == "baseline")

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

    if use_baseline_tier_metrics:
        straight_pass = metrics.straight_not_escalated_pct >= 0.85
        ambiguous_pass = metrics.ambiguous_escalated_pct >= 0.75
        edge_pass = metrics.edge_escalated_pct >= 1.0
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
    else:
        straight_pass = metrics.straight_accuracy >= 0.85
        ambiguous_pass = metrics.ambiguous_accuracy >= 0.75
        edge_pass = metrics.edge_accuracy >= 0.75
        print(
            "  Straightforward "
            f"({metrics.straight_total}) — Accuracy      : "
            f"{metrics.straight_accuracy * 100:.1f}%  "
            f"({metrics.straight_correct}/{metrics.straight_total})    "
            f"{'✓' if straight_pass else '✗'} target ≥ 85%"
        )
        print(
            "  Ambiguous       "
            f"({metrics.ambiguous_total}) — Accuracy      : "
            f"{metrics.ambiguous_accuracy * 100:.1f}% "
            f"({metrics.ambiguous_correct}/{metrics.ambiguous_total})    "
            f"{'✓' if ambiguous_pass else '✗'} target ≥ 75%"
        )
        print(
            "  Edge cases      "
            f"({metrics.edge_total}) — Accuracy      : "
            f"{metrics.edge_accuracy * 100:.1f}% "
            f"({metrics.edge_correct}/{metrics.edge_total})    "
            f"{'✓' if edge_pass else '✗'} target ≥ 75%"
        )

    print()
    print("Operational indicators:")
    print(
        f"  Retry attempted cases: {metrics.retry_attempted_count}/{metrics.total} "
        f"({(metrics.retry_attempted_count / metrics.total * 100) if metrics.total else 0.0:.1f}%)"
    )
    print(f"  Average confidence   : {metrics.avg_confidence:.3f}")
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


def _print_guardrails_section(
    outputs: list[DecisionOutput], cases: list[Case]
) -> None:
    """Print validation guardrail indicators and confidence calibration snapshot."""
    indicators = compute_guardrail_indicators(outputs, cases)
    expected_by_id = {case.case_id: case.expected_decision for case in cases}
    snapshot = confidence_calibration_snapshot(outputs, expected_by_id)

    print()
    print("------------------------------------------------------------")
    print("  Guardrail & calibration (observability)")
    print("------------------------------------------------------------")
    print(f"  Outputs analyzed     : {indicators.total_outputs}")
    print(
        f"  Citation drift       : {indicators.citation_drift_count} "
        f"({indicators.citation_drift_rate * 100:.1f}% of outputs, severity: {indicators.citation_drift_severity})"
    )
    print(f"  Input contradiction flags (case attrs) : {indicators.contradiction_flag_count}")
    print()
    print("  Confidence buckets (model output vs expected label accuracy):")
    for bucket, stats in snapshot.items():
        acc = stats.get("accuracy")
        acc_s = f", label accuracy {acc * 100:.1f}%" if acc is not None else ""
        print(
            f"    {bucket}: n={int(stats['count'])}, "
            f"avg_confidence={stats['avg_confidence']:.3f}{acc_s}"
        )


def _parse_eval_args() -> tuple[str, bool]:
    """Resolve evaluation mode, optional guardrails report, from CLI and environment."""
    parser = argparse.ArgumentParser(
        description="Run Orion evaluation in baseline or extended mode."
    )
    parser.add_argument(
        "--mode",
        choices=("baseline", "extended"),
        help="Evaluation mode (overrides EVAL_MODE if set).",
    )
    parser.add_argument(
        "--guardrails",
        action="store_true",
        help="After metrics, print citation-drift indicators and confidence calibration.",
    )
    args = parser.parse_args()

    env_mode = os.environ.get("EVAL_MODE", "").strip().lower()
    if args.mode:
        mode = args.mode
    elif env_mode in MODE_FILE_MAP:
        mode = env_mode
    else:
        mode = "baseline"
    return mode, args.guardrails


if __name__ == "__main__":
    start = time.time()
    results: list[EvalResult] = []
    guardrail_outputs: list[DecisionOutput] = []
    guardrail_cases: list[Case] = []

    mode, show_guardrails = _parse_eval_args()
    file_config = MODE_FILE_MAP[mode]
    cases_file = file_config["cases_file"]
    policies_file = file_config["policies_file"]

    with open(cases_file, "r", encoding="utf-8") as handle:
        raw_cases = json.load(handle)

    retriever = PolicyRetriever(policies_file)
    agent = DecisionAgent(retriever)

    print(f"Running evaluation mode: {mode}", file=sys.stderr)
    print(f"Using cases file: {cases_file}", file=sys.stderr)
    print(f"Using policies file: {policies_file}", file=sys.stderr)

    for index, raw_case in enumerate(raw_cases, start=1):
        raw_case_id = raw_case.get("case_id", f"UNKNOWN-{index:03d}")
        print(f"Processing {raw_case_id} ({index}/{len(raw_cases)})...", file=sys.stderr)

        expected = raw_case.get("expected_decision", "ESCALATE")
        difficulty = raw_case.get("difficulty", "edge")

        try:
            case = Case(**raw_case)
        except Exception as exc:
            print(f"Error while validating {raw_case_id}: {exc}", file=sys.stderr)
            results.append(
                EvalResult(
                    case_id=raw_case_id,
                    difficulty=difficulty,
                    expected=expected,
                    got="ESCALATE",
                    confidence=0.0,
                    retry_attempted=True,
                )
            )
            continue

        try:
            decision = run_pipeline(case, agent)
            got = decision.decision
            confidence = decision.confidence
            retry_attempted = decision.audit_log.retry_attempted
            if show_guardrails:
                guardrail_outputs.append(decision)
                guardrail_cases.append(case)
        except Exception as exc:
            print(f"Error while processing {raw_case_id}: {exc}", file=sys.stderr)
            got = "ESCALATE"
            confidence = 0.0
            retry_attempted = True

        results.append(
            EvalResult(
                case_id=raw_case_id,
                difficulty=difficulty,
                expected=expected,
                got=got,
                confidence=confidence,
                retry_attempted=retry_attempted,
            )
        )

    metrics = compute_metrics(results)
    runtime_s = time.time() - start
    _print_report(results, metrics, runtime_s, mode=mode)

    if show_guardrails and guardrail_outputs:
        _print_guardrails_section(guardrail_outputs, guardrail_cases)

    sys.exit(0 if metrics.accuracy >= 0.70 else 1)
