# Product Requirements Document (PRD)
## Project: Orion AI Decision Agent
**Version:** 1.0  
**Status:** Active  
**Owner:** Candidate  
**Last Updated:** 2025

---

## 1. Project Overview

### 1.1 Objective

Build a lightweight, production-quality AI decision agent that mimics the workflow of a human compliance operator in a regulated fintech environment. The agent must read incoming cases, retrieve relevant policy rules, and return a structured, auditable decision: **APPROVE**, **DENY**, or **ESCALATE**.

This is not a UI project. This is a reasoning reliability and systems design project. The goal is to demonstrate:
- Clean problem structuring
- Deliberate and grounded AI usage (not "magic" prompting)
- Mature handling of uncertainty and edge cases
- Consistent, inspectable, auditable outputs

### 1.2 Business Context

In fintech, human compliance operators routinely:
1. Receive a case (payout request, identity review, fraud flag)
2. Look up internal policy rules that apply to that case
3. Make a governed decision with justification
4. Escalate anything uncertain to a senior reviewer

Our system replicates this exact loop using an AI agent with policy retrieval grounding — not freeform LLM reasoning.

### 1.3 Success Criteria

| Criterion | Target |
|---|---|
| All 12–15 cases processed without runtime errors | 100% |
| Ambiguous cases escalated | ≥ 75% |
| Straightforward cases NOT escalated | ≥ 85% |
| Every decision has at least one policy citation | 100% |
| Output schema validates correctly via Pydantic | 100% |
| Retrieval failure handled gracefully | ESCALATE returned |
| Invalid LLM output retried once before ESCALATE | 100% |

---

## 2. Project Scope

### 2.1 In Scope

- `policies.md` — 7 well-structured fintech policy rules
- `cases.json` — 14 realistic test cases across 3 difficulty tiers
- `agent.py` — core decision agent with retrieval, decision, validation
- `retriever.py` — TF-IDF based semantic policy retrieval (no external DB)
- `validator.py` — Pydantic v2 schema validation + retry + escalation fallback
- `evaluate.py` — batch evaluation script with metrics printout
- `design.md` — short system design writeup (~1 page)
- `README.md` — setup instructions, how to run, env requirements
- `.env.example` — API key placeholder (never commit real keys)
- `tests/` — minimum 4 pytest unit tests covering critical logic

### 2.2 Out of Scope

- Any frontend or API server
- Vector databases or external embedding services
- Authentication, user management
- Production infrastructure or deployment
- Streaming or async agent loops

---

## 3. Functional Requirements

### FR-01: Policy File

- Stored as `policies.md` in project root
- **7 policies total**
- Each policy must contain:
  - `policy_id`: format `POL-00X`
  - `title`: short descriptive name
  - `rule`: clear if/then conditional statement (1–3 sentences)
  - `escalation_note`: edge case that triggers ESCALATE rather than DENY or APPROVE
- Policy topics must cover the realistic fintech domain: identity mismatch, payout thresholds, high-risk flags, velocity checks, missing data, account age, and conflict signals

### FR-02: Case Dataset

- Stored as `cases.json`
- **14 cases total**, distributed:
  - 8 straightforward (expected: APPROVE or DENY, high confidence)
  - 4 ambiguous (expected: ESCALATE, mixed signals)
  - 2 edge cases (expected: ESCALATE, missing/conflicting data)
- Each case contains:
  - `case_id`: format `CASE-XXX`
  - `summary`: 1–2 sentence natural language description
  - `attributes`: structured object with typed fields
  - `expected_decision`: ground truth label for evaluation
  - `difficulty`: `"straightforward"`, `"ambiguous"`, or `"edge"`
- Case attributes must include (where relevant): `case_type`, `payout_amount`, `identity_verified`, `verified_name`, `account_holder_name`, `recent_profile_changes`, `high_risk_flag`, `account_age_days`, `missing_fields`, `transaction_velocity`

### FR-03: Policy Retrieval

- Function signature: `search_policies(query: str, top_k: int = 3) -> list[Policy]`
- Implementation: TF-IDF vectorizer + cosine similarity (scikit-learn)
- Must return top-k most relevant policies by similarity score
- Must handle empty results gracefully (return empty list, not raise exception)
- Retrieval is triggered **before** the LLM decision call — always
- Retrieved policy IDs are passed into the prompt context

### FR-04: Decision Agent

- Accepts one case as input
- Sends case + retrieved policy text to Claude API (claude-sonnet-4-5)
- System prompt enforces: only cite policies provided, return strict JSON, escalate if uncertain
- Agent raw response JSON contains: `decision`, `confidence`, `policy_citations` only
- Final pipeline output (post-validator) returns structured JSON with: `case_id`, `decision`, `confidence`, `policy_citations`, `audit_log`
- The agent must never make a decision without running retrieval first

### FR-05: Output Validation

- All agent output validated against a Pydantic v2 model before returning
- If validation fails: retry once with a correction prompt
- If second attempt fails: return ESCALATE with `confidence=0.0` and error in audit log
- No unvalidated output is ever returned to the caller

### FR-06: Escalation Logic

The agent must ESCALATE when:
- Confidence score returned by LLM < 0.65 (configurable threshold)
- `missing_fields` is non-empty in case attributes
- Conflicting signals detected (e.g., identity_verified=true but name mismatch)
- Policy retrieval returns zero results
- Output fails validation twice

### FR-07: Evaluation Script

- `evaluate.py` runs all cases from `cases.json`
- Prints the following metrics:
  ```
  Total cases: 14
  Approve: X  |  Deny: X  |  Escalate: X
  
  Accuracy vs expected labels: XX%
  Ambiguous cases escalated: X/4 (XX%)
  Straightforward cases NOT escalated: X/8 (XX%)
  Edge cases escalated: X/2 (XX%)
  
  --- Per-case log ---
  CASE-001 | Expected: APPROVE | Got: APPROVE | PASS ✓
  CASE-002 | Expected: ESCALATE | Got: DENY   | FAIL ✗
  ...
  ```

---

## 4. Non-Functional Requirements

### NFR-01: Reliability
- No case should crash the pipeline. All exceptions are caught and handled by returning ESCALATE.
- Retry logic on validation failure as described in FR-05.

### NFR-02: Auditability
- Every decision response includes a populated `audit_log` containing:
  - `retrieved_policies`: list of policy IDs retrieved
  - `timestamp`: ISO 8601 UTC
  - `retrieval_score`: top similarity score from retrieval
  - `retry_attempted`: boolean

### NFR-03: No Hardcoded Decision Logic
- No `if payout_amount > 1000: return DENY` anywhere in the code
- All decisions are made by the LLM grounded in retrieved policy text
- The only hardcoded logic allowed: escalation fallback triggers (FR-06)

### NFR-04: Clean Code Structure
- Each module has a single responsibility
- No function longer than 50 lines
- All public functions have type hints
- Constants (confidence threshold, top_k, model name) live in `config.py`

### NFR-05: Security
- API key loaded from `.env` via `python-dotenv`
- `.env` is in `.gitignore` — never committed
- No secrets in code, logs, or audit output

### NFR-06: Reproducibility
- `requirements.txt` pins all dependencies with exact versions
- README documents exact Python version (3.11+)

---

## 5. System Inputs & Outputs

### 5.1 Input (per case)

```json
{
  "case_id": "CASE-007",
  "summary": "Customer submitted a payout request...",
  "attributes": {
    "case_type": "payout_review",
    "payout_amount": 1800,
    "identity_verified": true,
    "verified_name": "Jordan Lee",
    "account_holder_name": "J. Smith",
    "recent_profile_changes": 2,
    "high_risk_flag": false,
    "account_age_days": 45,
    "missing_fields": [],
    "transaction_velocity": 3
  },
  "expected_decision": "ESCALATE",
  "difficulty": "ambiguous"
}
```

### 5.2 Output (strict JSON)

```json
{
  "case_id": "CASE-007",
  "decision": "ESCALATE",
  "confidence": 0.52,
  "policy_citations": [
    {
      "policy_id": "POL-003",
      "reason": "Account holder name does not match verified identity on file."
    },
    {
      "policy_id": "POL-005",
      "reason": "Two profile changes within 24 hours triggers velocity review."
    }
  ],
  "audit_log": {
    "retrieved_policies": ["POL-003", "POL-005", "POL-007"],
    "retrieval_score": 0.74,
    "timestamp": "2025-01-15T14:32:01Z",
    "retry_attempted": false
  }
}
```

---

## 6. Architecture Flow (High Level)

```
Input Case
    |
    v
[CaseLoader] — validates case schema, flags missing_fields
    |
    v
[PolicyRetriever] — TF-IDF cosine similarity, returns top-3 policies
    |         |
    |         +---> retrieval failure → ESCALATE immediately
    v
[DecisionAgent] — sends case + policies to Claude API
    |
    v
[OutputValidator] — Pydantic v2 validation
    |         |
    |         +---> fail → retry once → fail again → ESCALATE
    v
[EscalationChecker] — applies FR-06 rules post-validation
    |
    v
Structured Decision Output (JSON)
```

---

## 7. Technology Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| LLM | Anthropic Claude (claude-sonnet-4-5) | latest |
| Anthropic SDK | `anthropic` | 0.26+ |
| Policy Retrieval | `scikit-learn` TF-IDF | 1.4+ |
| Output Validation | `pydantic` | v2.6+ |
| Env Config | `python-dotenv` | 1.0+ |
| Testing | `pytest` | 8.0+ |
| Mocking | `pytest-mock` | 3.12+ |

**No LangChain. No vector database. No FastAPI.**  
Deliberate simplicity is a feature, not a limitation.

---

## 8. File Structure

```
orion-decision-agent/
├── README.md
├── design.md
├── policies.md
├── cases.json
├── requirements.txt
├── .env.example
├── .gitignore
├── config.py                  # constants: threshold, top_k, model name
├── models.py                  # Pydantic models: Case, Policy, DecisionOutput
├── retriever.py               # TF-IDF search_policies()
├── agent.py                   # core LLM decision logic
├── validator.py               # output validation + retry
├── evaluate.py                # batch evaluation + metrics
└── tests/
    ├── test_retriever.py
    ├── test_validator.py
    ├── test_agent.py
    └── test_evaluate.py
```

---

## 9. Constraints & Assumptions

- The assignment targets 2–4 hours of effort; we are intentionally targeting 6–8 hours of well-documented, well-tested work to stand out.
- We use our own Anthropic API key stored in `.env`. Estimated API cost for full test run: < $0.20.
- No UI is built. The deliverable is a clean Python package.
- All decisions are returned synchronously (no async).
- Policy retrieval is stateless — no caching needed at this scale.
- The cases.json `expected_decision` labels are used only for evaluation, not fed into the agent.

---

## 10. Implementation Special Instructions

These instructions govern how the code must be written. Any AI-assisted coding (Cursor, etc.) must follow these:

1. **No hardcoded decision logic.** The LLM decides. Code only enforces structure and fallbacks.
2. **Retrieval happens first, always.** The agent function must call `search_policies()` before calling the API. This is non-negotiable and must be visible in the code flow.
3. **Confidence is computed by the LLM but bounded.** The prompt asks the LLM to return a confidence float 0.0–1.0. The validator ensures it is within range. The escalation checker applies the threshold (default: 0.65).
4. **The system prompt is concise and instructional.** It must: (a) describe the agent's role, (b) list the retrieved policies inline, (c) specify the exact JSON output schema, (d) instruct the model to ESCALATE when uncertain.
5. **Policy citations must only reference retrieved policies.** The validator must check that every cited `policy_id` was in the retrieved set. If not — flag in audit_log.
6. **All edge cases return ESCALATE, never crash.** Use try/except at every I/O boundary (API call, file read, JSON parse).
7. **Evaluation script uses expected_decision labels.** Accuracy is `sum(got == expected) / total`. Do not manipulate this number.
8. **Write real tests.** At least one test must mock the Anthropic API call. At least one test must cover the retry-then-escalate path.

---

*Next Document: System Design & Architecture*
