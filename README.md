# Orion AI Decision Agent

Policy-grounded compliance decisioning for payout-review cases: structured `APPROVE` / `DENY` / `ESCALATE` outputs with audit metadata and schema validation.

Implementation notes: how **prompts** are structured (`agent.py`: `SYSTEM_PROMPT`, `build_user_message`) and how the pipeline runs end-to-end (retrieve → call model → validate → deterministic safety checks). Live model outputs can vary run to run; the reliability comes from the pipeline contracts and guardrails.

## Requirements

- Python `3.11+` recommended (the project also runs on `3.9` in some environments; target the assignment’s `3.11+` when you can)
- Anthropic API key with access to `claude-sonnet-4-5`
- Dependencies are pinned in `requirements.txt`

## Setup

1. Clone the repository

```bash
git clone <your-repo-url>
cd mogo
```

1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\activate
```

1. Install dependencies

```bash
pip install -r requirements.txt
```

1. Configure environment variables

```bash
cp .env
```

`.env` contents:

```env
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

Set your real `ANTHROPIC_API_KEY` in `.env`.

1. Optional sanity check (messages go to **stderr**)

```bash
python3 retriever.py
```

Example:

```text
Setup validated: 7 policies, 14 cases loaded.
```

## Running the evaluation

Progress lines (`Processing CASE-…`) are printed to **stderr**; the report below is **stdout** (so you can `>` redirect the report only).

### Baseline (default)

```bash
python3 evaluate.py
```

Example report from one successful run (model outputs can vary slightly; tier targets match the original assignment rubric):

```text
============================================================
  ORION DECISION AGENT — EVALUATION REPORT
============================================================

Total cases run : 14
Approve         : 4
Deny            : 4
Escalate        : 6

Overall accuracy (vs labels) : 100.0%  (14/14)

By difficulty tier:
  Straightforward (8) — NOT escalated : 100.0%  (8/8)    ✓ target ≥ 85%
  Ambiguous       (4) — Escalated     : 100.0% (4/4)    ✓ target ≥ 75%
  Edge cases      (2) — Escalated     : 100.0% (2/2)    ✓ target 100%

Operational indicators:
  Retry attempted cases: 0/14 (0.0%)
  Average confidence   : 0.776

------------------------------------------------------------
  Per-case breakdown
------------------------------------------------------------
  CASE-001 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-002 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-003 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-004 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-005 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-006 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-007 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-008 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-009 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-010 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-011 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-012 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-013 | edge            | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-014 | edge            | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
============================================================
Runtime: 56.85s
```

Exit code: `0` if overall accuracy ≥ 70%, else `1`.

### Extended mode

```bash
python3 evaluate.py --mode extended
```

Same pipeline; uses `cases_extended.json` and `policies_extended.md`. Tier lines use **per-tier accuracy** (because edge cases can expect `DENY` as well as `ESCALATE`). Example from one evaluation run:

```text
============================================================
  ORION DECISION AGENT — EVALUATION REPORT
============================================================

Total cases run : 12
Approve         : 2
Deny            : 4
Escalate        : 6

Overall accuracy (vs labels) : 100.0%  (12/12)

By difficulty tier:
  Straightforward (3) — Accuracy      : 100.0%  (3/3)    ✓ target ≥ 85%
  Ambiguous       (5) — Accuracy      : 100.0% (5/5)    ✓ target ≥ 75%
  Edge cases      (4) — Accuracy      : 100.0% (4/4)    ✓ target ≥ 75%

Operational indicators:
  Retry attempted cases: 0/12 (0.0%)
  Average confidence   : 0.711

------------------------------------------------------------
  Per-case breakdown
------------------------------------------------------------
  CASE-201 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-202 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-203 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-204 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-205 | ambiguous       | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-206 | edge            | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-207 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-208 | edge            | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-209 | edge            | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-210 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-211 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-212 | edge            | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
============================================================
Runtime: 76.34s
```

Optional environment selector: `EVAL_MODE=extended python3 evaluate.py`

Optional observability after the report (citation drift + confidence buckets vs labels):

```bash
python3 evaluate.py --guardrails
python3 evaluate.py --mode extended --guardrails
```

## Running a single case

Full pipeline smoke (`CASE-001`, `CASE-013`) — uses live API:

```bash
python3 validator.py
```

Raw model output only (still goes through retrieval in `agent.decide`):

```bash
python3 agent.py
```

## Running tests

```bash
pytest tests/ -v
```

No API calls in tests (Anthropic usage is mocked). Latest run: **29 passed**.

## Project structure

- `config.py` — constants, thresholds, env loading
- `models.py` — Pydantic input/output contracts
- `retriever.py` — policy markdown parsing, TF-IDF retrieval, query enrichment, setup check
- `agent.py` — system/user prompts, API wrapper, `DecisionAgent`
- `validator.py` — JSON parse, Pydantic validation, retry, `EscalationChecker`, `run_pipeline`
- `evaluate.py` — batch run, metrics, `--mode`, optional `--guardrails`
- `policies.md` / `cases.json` — baseline policies (7) and cases (14)
- `policies_extended.md` / `cases_extended.json` — optional harder corpus
- `design.md` — short design write-up (assignment format)
- `tests/` — unit, contract, and stress tests

## Design decisions

Ground decisions in **retrieved policy text**, enforce shape with **Pydantic**, and treat **ESCALATE** as a normal governed outcome when confidence is low, data is missing, retrieval fails, validation fails after retry, or structural identity checks fire. The one-page narrative alongside this README is in `design.md`.

## Architecture (component map & data flow)

**Component map**

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRY POINTS                             │
│                                                                 │
│    evaluate.py (batch)              agent.py (single case)      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PIPELINE LAYER                             │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│  │ CaseLoader  │───▶│PolicyRetriever│──▶│  DecisionAgent     │  │
│  │ (models.py) │    │(retriever.py)│    │  (agent.py)        │  │
│  └─────────────┘    └──────────────┘    └────────────────────┘  │
│                                                  │              │
│                                                  ▼              │
│                                        ┌──────────────────────┐ │
│                                        │  OutputValidator     │ │
│                                        │  (validator.py)      │ │
│                                        └──────────────────────┘ │
│                                                  │              │
│                                                  ▼              │
│                                        ┌──────────────────────┐ │
│                                        │  EscalationChecker   │ │
│                                        │  (validator.py)      │ │
│                                        └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                         │
│                                                                 │
│  ┌──────────────┐   ┌───────────────┐   ┌───────────────────┐   │
│  │  config.py   │   │  models.py    │   │  Anthropic SDK    │   │
│  │  (constants) │   │  (contracts)  │   │  (API client)     │   │
│  └──────────────┘   └───────────────┘   └───────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**End-to-end data flow**

```
cases.json (or cases_extended.json)
    │
    │ read + parse
    ▼
Case (Pydantic model)
    │
    │ extract summary + attributes
    ▼
PolicyRetriever.search(query)  ◀── policies markdown (loaded at startup)
    │
    │ top-k Policy objects by cosine similarity
    ▼
build_user_message(case, policies) + SYSTEM_PROMPT
    │
    │ system + user messages
    ▼
Anthropic API  →  raw JSON string
    │
    │ parse + validate (+ retry on failure)
    ▼
DecisionOutput (Pydantic model)  ◀── or ESCALATE fallback
    │
    │ EscalationChecker (threshold, missing fields, empty retrieval, identity checks)
    ▼
Final DecisionOutput
    │
    │ stdout / metrics in evaluate.py
    ▼
Metrics + per-case log
```

## Metrics (how to read the report)

- **Baseline** tiers: “NOT escalated” / “Escalated” percentages match the original assignment’s difficulty rubric (all baseline edge cases expect `ESCALATE`).
- **Extended** tiers: “Accuracy” = fraction of cases in that tier where `got == expected` (edge bucket mixes `DENY` and `ESCALATE` labels).
- **Retry attempted** = output failed schema/JSON once and succeeded (or exhausted) on correction path.
- **Overall accuracy** = label match rate; **exit code** follows the ≥70% rule in `evaluate.py`.

## Troubleshooting

- Use `python3` if `python` is missing on your PATH.
- Confirm `.env` contains a valid `ANTHROPIC_API_KEY`.
- Full evaluation issues many API calls (~1–2+ minutes); watch stderr for progress.
- For debugging one case, use `validator.py` and read `audit_log.error_detail` when present.

**Known nuance:** `python3 agent.py` may show the model wrapping JSON in markdown fences; `validator.py` strips fences before parsing, so the full pipeline remains robust even if the smoke raw line looks noisy.