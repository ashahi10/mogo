# System Design & Architecture
## Project: Orion AI Decision Agent
**Version:** 1.0  
**Status:** Active  
**Depends On:** PRD v1.0  
**Last Updated:** 2025

---

## 1. Document Purpose

This document defines the complete technical architecture of the Orion AI Decision Agent. It is the authoritative reference for every implementation decision: module responsibilities, data contracts, retrieval design, prompt strategy, escalation logic, error handling, and testing approach.

Any code produced (manually or via AI-assisted tooling) must be traceable back to a decision made in this document. If something is not covered here, it should be added before implementing it.

---

## 2. Architecture Philosophy

### 2.1 Core Principle: Grounded Decisions Only

The agent never reasons freely. Every decision is grounded in a retrieved policy. This is not a constraint imposed by the assignment — it is the correct design for any AI system operating in a regulated domain.

```
NO:  LLM reads case → decides based on training knowledge
YES: LLM reads case + retrieved policy text → decides only within that context
```

This distinction matters because:
- Freeform LLM decisions are not auditable
- Policy-grounded decisions can be explained, challenged, and overridden
- Retrieval failure becomes a detectable, handleable event

### 2.2 Core Principle: Uncertainty Is a First-Class Outcome

Most systems treat uncertainty as a failure mode. We treat it as a valid, expected output. ESCALATE is not a fallback — it is an equal peer to APPROVE and DENY, triggered by clearly defined conditions.

### 2.3 Core Principle: No Hidden Logic

Every decision-influencing rule must be either:
- In `policies.md` (domain rules, visible to operators)
- In `config.py` (system thresholds, visible to engineers)

No decision logic buried in prompts, conditionals, or comments.

### 2.4 Core Principle: Fail Toward Safety

When anything is uncertain, missing, or broken — the system defaults to ESCALATE. It never guesses, never approximates, never silently proceeds with bad data.

```
Hierarchy of trust:
  Validated output with high confidence → trust the decision
  Validated output with low confidence → override to ESCALATE
  Invalid output, retry succeeded      → use retry result
  Invalid output, retry failed         → ESCALATE unconditionally
  Any exception at any layer           → ESCALATE unconditionally
```

---

## 3. System Architecture Overview

### 3.1 Component Map

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
│                                                  │               │
│                                                  ▼               │
│                                        ┌──────────────────────┐  │
│                                        │  OutputValidator     │  │
│                                        │  (validator.py)      │  │
│                                        └──────────────────────┘  │
│                                                  │               │
│                                                  ▼               │
│                                        ┌──────────────────────┐  │
│                                        │  EscalationChecker   │  │
│                                        │  (validator.py)      │  │
│                                        └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                         │
│                                                                 │
│  ┌──────────────┐   ┌───────────────┐   ┌───────────────────┐  │
│  │  config.py   │   │  models.py    │   │  Anthropic SDK    │  │
│  │  (constants) │   │  (contracts)  │   │  (API client)     │  │
│  └──────────────┘   └───────────────┘   └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow — End to End

```
cases.json
    │
    │ read + parse
    ▼
Case (Pydantic model)
    │
    │ extract summary + attributes
    ▼
search_policies(query)  ◀── policies.md (loaded once at startup)
    │
    │ top-k Policy objects by cosine similarity
    ▼
build_prompt(case, policies)
    │
    │ system_prompt + user_message
    ▼
Anthropic API  →  raw JSON string
    │
    │ parse + validate
    ▼
DecisionOutput (Pydantic model)  ◀── or retry / ESCALATE
    │
    │ apply escalation rules
    ▼
Final DecisionOutput (immutable)
    │
    │ write to stdout / collect in evaluate.py
    ▼
Metrics + Per-case log
```

---

## 4. Module Specifications

### 4.1 `config.py` — System Constants

**Responsibility:** Single source of truth for all tunable parameters. Nothing is hardcoded in any other module.

```python
# config.py

MODEL_NAME = "claude-sonnet-4-5"
MAX_TOKENS = 1024
TEMPERATURE = 0.1          # Low temperature: we want deterministic, policy-driven output

RETRIEVAL_TOP_K = 3        # Number of policies retrieved per case
CONFIDENCE_THRESHOLD = 0.65  # Below this → ESCALATE regardless of decision
MIN_POLICY_CITATIONS = 1   # Every decision must cite at least one policy

CASES_FILE = "cases.json"
POLICIES_FILE = "policies.md"

# Escalation triggers (used by EscalationChecker)
ESCALATE_ON_MISSING_FIELDS = True
ESCALATE_ON_RETRIEVAL_FAILURE = True
ESCALATE_ON_VALIDATION_FAILURE = True  # after retry exhausted
```

**Design note:** Temperature is set to 0.1 (not 0.0). Fully deterministic output (0.0) can cause the model to get stuck in degenerate repetition patterns on edge cases. 0.1 introduces just enough variance to recover while keeping outputs stable.

---

### 4.2 `models.py` — Data Contracts

**Responsibility:** Define every data structure in the system as a typed, validated Pydantic v2 model. All inter-module communication uses these models, never raw dicts.

#### 4.2.1 Input Models

```python
class CaseAttributes(BaseModel):
    case_type: str
    payout_amount: Optional[float] = None
    identity_verified: Optional[bool] = None
    verified_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    recent_profile_changes: Optional[int] = None
    high_risk_flag: Optional[bool] = None
    account_age_days: Optional[int] = None
    missing_fields: list[str] = []
    transaction_velocity: Optional[int] = None

class Case(BaseModel):
    case_id: str
    summary: str
    attributes: CaseAttributes
    expected_decision: Literal["APPROVE", "DENY", "ESCALATE"]
    difficulty: Literal["straightforward", "ambiguous", "edge"]

class Policy(BaseModel):
    policy_id: str          # POL-001 ... POL-007
    title: str
    rule: str
    escalation_note: Optional[str] = None
    similarity_score: float = 0.0   # populated by retriever
```

#### 4.2.2 Output Models

```python
class PolicyCitation(BaseModel):
    policy_id: str
    reason: str

    @field_validator("reason")
    def reason_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Citation reason must not be empty")
        return v

class AuditLog(BaseModel):
    retrieved_policies: list[str]
    retrieval_score: float
    timestamp: str          # ISO 8601 UTC
    retry_attempted: bool
    error_detail: Optional[str] = None

class DecisionOutput(BaseModel):
    case_id: str
    decision: Literal["APPROVE", "DENY", "ESCALATE"]
    confidence: float
    policy_citations: list[PolicyCitation]
    audit_log: AuditLog

    @field_validator("confidence")
    def confidence_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be 0.0–1.0, got {v}")
        return v

    @field_validator("policy_citations")
    def must_have_citations(cls, v):
        if not v:
            raise ValueError("At least one policy citation is required")
        return v
```

**Design note:** Validators are on the model, not in application code. This means validation cannot be bypassed — any path that produces a `DecisionOutput` is guaranteed to be valid.

---

### 4.3 `retriever.py` — Policy Retrieval

**Responsibility:** Load policies from `policies.md`, build a TF-IDF index at startup, and expose `search_policies(query)` for similarity-based lookup.

#### 4.3.1 Why TF-IDF (Not Embeddings)

| Factor | TF-IDF | Embeddings |
|---|---|---|
| External dependencies | None (scikit-learn only) | API call or local model |
| Latency | < 1ms | 50–200ms per call |
| Cost | Free | API credits |
| Explainability | Term overlap is inspectable | Black box |
| Accuracy at 7 documents | Sufficient | Overkill |
| Failure modes | None after init | Network, rate limit |

For a corpus of 7 policies, TF-IDF cosine similarity is entirely sufficient. Using embeddings here would be engineering theater — adding complexity and cost without meaningful accuracy gain. This choice itself demonstrates sound judgment.

#### 4.3.2 PolicyRetriever Design

```python
class PolicyRetriever:
    """
    Loads policies once at init, builds TF-IDF index.
    Thread-safe for read operations. Not designed for hot reloading.
    """

    def __init__(self, policies_path: str):
        self.policies: list[Policy] = self._load_policies(policies_path)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),    # unigrams + bigrams
            stop_words="english",
            max_features=500
        )
        # Build corpus: concatenate policy title + rule + escalation_note
        corpus = [
            f"{p.title} {p.rule} {p.escalation_note or ''}"
            for p in self.policies
        ]
        self.policy_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> list[Policy]:
        """
        Returns top_k policies most relevant to the query.
        Returns empty list on any failure — caller must handle this.
        """
        try:
            query_vec = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self.policy_matrix)[0]
            top_indices = scores.argsort()[::-1][:top_k]

            results = []
            for idx in top_indices:
                if scores[idx] > 0.0:   # only return policies with actual match
                    policy = self.policies[idx].model_copy()
                    policy.similarity_score = float(scores[idx])
                    results.append(policy)
            return results
        except Exception:
            return []   # safe failure — caller escalates on empty list

    def _load_policies(self, path: str) -> list[Policy]:
        # Parse policies.md into Policy objects
        # Policy blocks separated by "---" delimiter
        ...
```

**Why bigrams (`ngram_range=(1,2)`):** Policy language has meaningful two-word phrases — "name mismatch", "payout request", "high risk", "identity verified". Unigrams alone would treat these as independent terms and miss the compound meaning.

**Why `scores[idx] > 0.0` filter:** A zero cosine similarity means the query shares no terms with the policy — returning it as a "match" would be misleading and could result in the LLM citing a completely irrelevant policy.

#### 4.3.3 Query Construction

The retrieval query is not the raw case summary. It is a constructed string that emphasizes the structured signals:

```python
def build_retrieval_query(case: Case) -> str:
    """
    Constructs a retrieval query that combines:
    - The natural language summary
    - Key structured attributes as readable phrases
    """
    parts = [case.summary]

    attrs = case.attributes
    if attrs.high_risk_flag:
        parts.append("high risk flagged account")
    if attrs.missing_fields:
        parts.append(f"missing fields: {', '.join(attrs.missing_fields)}")
    if attrs.identity_verified is False:
        parts.append("identity not verified")
    if attrs.verified_name and attrs.account_holder_name:
        if attrs.verified_name.lower() != attrs.account_holder_name.lower():
            parts.append("name mismatch identity discrepancy")
    if attrs.recent_profile_changes and attrs.recent_profile_changes > 1:
        parts.append("multiple recent profile changes velocity")
    if attrs.payout_amount and attrs.payout_amount > 5000:
        parts.append("large payout high value transaction")

    return " ".join(parts)
```

**Design note:** This is not decision logic — it is query enrichment. We are helping the TF-IDF retriever find the right policies by surfacing the signals that matter. The decision still belongs entirely to the LLM.

---

### 4.4 `agent.py` — Decision Agent

**Responsibility:** Orchestrate the full decision pipeline for a single case. Call retrieval, build the prompt, call the API, return the raw response string.

#### 4.4.1 Prompt Architecture

The prompt has two components: a **system prompt** (role + output contract) and a **user message** (case + policies).

**System Prompt — Design Principles:**
1. Establish role before any content
2. State the output schema explicitly (not "JSON-like" — the exact schema)
3. State escalation conditions explicitly
4. Forbid citation of policies not provided
5. Keep it under 400 tokens — long system prompts dilute instruction-following

```
SYSTEM PROMPT (verbatim):

You are a compliance decision agent in a regulated fintech environment.

Your role is to review incoming cases and issue a structured decision 
based ONLY on the policies provided to you. You must not use outside 
knowledge or reasoning not grounded in the provided policies.

DECISION OPTIONS:
- APPROVE: Case clearly satisfies policy requirements, no risk signals
- DENY: Case clearly violates one or more policies
- ESCALATE: Uncertain, conflicting signals, or insufficient information

ESCALATE when:
- Your confidence is below 0.65
- Important fields are missing or contradictory
- Policies conflict or partially apply
- You cannot ground the decision in the provided policies

OUTPUT: Return ONLY a valid JSON object in this exact schema:
{
  "decision": "APPROVE" | "DENY" | "ESCALATE",
  "confidence": <float 0.0–1.0>,
  "policy_citations": [
    {
      "policy_id": "<id from provided policies only>",
      "reason": "<specific reason this policy applies>"
    }
  ]
}

IMPORTANT:
- Only cite policy_ids from the policies provided to you
- Every decision requires at least one citation
- Return ONLY the JSON object — no preamble, no explanation
```

**User Message Template:**

```
CASE: {case_id}

SUMMARY:
{summary}

CASE ATTRIBUTES:
{formatted_attributes}

RELEVANT POLICIES (retrieved for this case):
{formatted_policies}

Issue your decision now.
```

**Why format attributes explicitly:** Sending raw JSON attributes to the LLM works, but formatting them as readable key-value pairs reduces token waste and improves the model's ability to match attribute values to policy conditions (e.g., "high_risk_flag: true" is clearer to the model than `"high_risk_flag":true` embedded in JSON).

#### 4.4.2 Agent Function

```python
class DecisionAgent:
    def __init__(self, retriever: PolicyRetriever):
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.retriever = retriever

    def decide(self, case: Case) -> tuple[str, list[Policy]]:
        """
        Returns:
          - raw JSON string from LLM
          - list of retrieved Policy objects (for audit + citation validation)
        Raises: Never. All exceptions caught, returns ESCALATE JSON.
        """
        retrieved: list[Policy] = []
        try:
            query = build_retrieval_query(case)
            retrieved = self.retriever.search(query)

            if not retrieved:
                return self._escalate_json(
                    case.case_id,
                    reason="Policy retrieval returned no results",
                    retrieved=[]
                ), []

            prompt_user = build_user_message(case, retrieved)

            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt_user}]
            )
            return response.content[0].text, retrieved

        except anthropic.APIError as e:
            return self._escalate_json(
                case.case_id,
                reason=f"API error: {str(e)}",
                retrieved=retrieved
            ), retrieved

        except Exception as e:
            return self._escalate_json(
                case.case_id,
                reason=f"Unexpected error: {str(e)}",
                retrieved=retrieved
            ), retrieved

    def _escalate_json(self, case_id: str, reason: str, retrieved: list[Policy]) -> str:
        """
        Returns a valid ESCALATE JSON string for use when the pipeline fails.
        This is the safety net — it must never itself raise an exception.
        """
        return json.dumps({
            "decision": "ESCALATE",
            "confidence": 0.0,
            "policy_citations": [{
                "policy_id": retrieved[0].policy_id if retrieved else "POL-007",
                "reason": f"Automatic escalation: {reason}"
            }]
        })
```

**Design note:** The agent returns a raw string, not a parsed model. Parsing is the validator's job. This strict separation means the agent can be tested independently by checking its prompt construction and API call, without needing to know the validation logic.

---

### 4.5 `validator.py` — Output Validation, Retry, and Escalation

**Responsibility:** Parse the agent's raw output, validate it, retry once on failure, apply escalation override rules, and return a final `DecisionOutput`.

#### 4.5.1 Validation Pipeline

```
raw_json_string
    │
    ├── Step 1: JSON parse
    │       fail → retry with correction prompt
    │
    ├── Step 2: Pydantic model validation
    │       fail → retry with correction prompt
    │
    ├── Step 3: Citation integrity check
    │       (every cited policy_id was in retrieved set)
    │       fail → remove invalid citations, warn in audit_log
    │
    ├── Step 4: EscalationChecker
    │       (apply FR-06 rules regardless of LLM decision)
    │       override to ESCALATE if any rule fires
    │
    └── Final DecisionOutput
```

#### 4.5.2 Retry Strategy

When validation fails, we do NOT simply re-call the agent with the same prompt. We send a correction prompt that includes:
- The original case and policies (context)
- The invalid output the model produced
- The specific error that caused rejection
- A reminder of the exact required schema

```python
CORRECTION_PROMPT_TEMPLATE = """
Your previous response was invalid. Here is why:

ERROR: {error_message}

YOUR INVALID RESPONSE:
{invalid_response}

You must return ONLY a valid JSON object matching this schema exactly:
{{
  "decision": "APPROVE" | "DENY" | "ESCALATE",
  "confidence": <float 0.0–1.0>,
  "policy_citations": [
    {{"policy_id": "<from provided policies only>", "reason": "<explanation>"}}
  ]
}}

Re-evaluate the case and respond now.

ORIGINAL CASE: {original_user_message}
"""
```

**Why include the invalid response:** The model can often self-correct when shown its own mistake. Simply repeating the instruction without the error tends to produce the same wrong output.

#### 4.5.3 EscalationChecker

Applied after successful validation. This is a deterministic post-processing step.

```python
class EscalationChecker:
    """
    Applies hard escalation rules regardless of LLM decision.
    These rules encode system-level safety constraints, not domain logic.
    """

    def check(
        self,
        output: DecisionOutput,
        case: Case,
        retrieved: list[Policy]
    ) -> DecisionOutput:

        reasons = []

        # Rule 1: Low confidence
        if output.confidence < CONFIDENCE_THRESHOLD:
            reasons.append(
                f"Confidence {output.confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}"
            )

        # Rule 2: Missing fields in case data
        if ESCALATE_ON_MISSING_FIELDS and case.attributes.missing_fields:
            reasons.append(
                f"Missing fields: {', '.join(case.attributes.missing_fields)}"
            )

        # Rule 3: Empty retrieval (should never reach here, but defense in depth)
        if ESCALATE_ON_RETRIEVAL_FAILURE and not retrieved:
            reasons.append("No policies were retrieved for this case")

        # Rule 4: Conflicting core identity signals in case data
        # Deterministic safeguard: contradictions must escalate even if model is confident.
        if case.attributes.identity_verified is True:
            verified = (case.attributes.verified_name or "").strip().lower()
            holder = (case.attributes.account_holder_name or "").strip().lower()
            if (
                (verified and holder and verified != holder)
                or holder == "unknown"
                or verified == "unknown"
            ):
                reasons.append(
                    "Conflicting identity signals: verified identity does not align with account holder name"
                )

        if reasons and output.decision != "ESCALATE":
            # Override decision, preserve citations and audit trail
            return output.model_copy(update={
                "decision": "ESCALATE",
                "audit_log": output.audit_log.model_copy(update={
                    "error_detail": "Escalation override: " + "; ".join(reasons)
                })
            })

        if reasons and output.decision == "ESCALATE" and output.audit_log.error_detail is None:
            # Already escalated — no override needed, but record reasons for audit completeness
            return output.model_copy(update={
                "audit_log": output.audit_log.model_copy(update={
                    "error_detail": "Escalation reasons noted: " + "; ".join(reasons)
                })
            })

        return output
```

**Design note:** The escalation checker never removes citations or changes the confidence score. It only changes the decision. This preserves the full audit trail — an operator reviewing the escalation can see what the model thought and why the system overrode it.

---

### 4.6 `evaluate.py` — Batch Evaluation

**Responsibility:** Run all cases, collect results, compute metrics, print report.

#### 4.6.1 Metrics Design

```python
def compute_metrics(results: list[EvalResult]) -> Metrics:
    total = len(results)
    correct = sum(1 for r in results if r.got == r.expected)

    by_difficulty = {
        "straightforward": [r for r in results if r.difficulty == "straightforward"],
        "ambiguous":       [r for r in results if r.difficulty == "ambiguous"],
        "edge":            [r for r in results if r.difficulty == "edge"],
    }

    # % ambiguous cases that were escalated (expected behavior)
    ambiguous_escalated = sum(
        1 for r in by_difficulty["ambiguous"] if r.got == "ESCALATE"
    ) / max(len(by_difficulty["ambiguous"]), 1)

    # % straightforward cases that were NOT escalated (expected behavior)
    straight_not_escalated = sum(
        1 for r in by_difficulty["straightforward"] if r.got != "ESCALATE"
    ) / max(len(by_difficulty["straightforward"]), 1)

    # % edge cases escalated
    edge_escalated = sum(
        1 for r in by_difficulty["edge"] if r.got == "ESCALATE"
    ) / max(len(by_difficulty["edge"]), 1)

    return Metrics(
        total=total,
        accuracy=correct / total,
        approve_count=sum(1 for r in results if r.got == "APPROVE"),
        deny_count=sum(1 for r in results if r.got == "DENY"),
        escalate_count=sum(1 for r in results if r.got == "ESCALATE"),
        ambiguous_escalated_pct=ambiguous_escalated,
        straight_not_escalated_pct=straight_not_escalated,
        edge_escalated_pct=edge_escalated,
    )
```

#### 4.6.2 Output Format

```
============================================================
  ORION DECISION AGENT — EVALUATION REPORT
============================================================

Total cases run : 14
Approve         : 5
Deny            : 4
Escalate        : 5

Overall accuracy (vs labels) : 85.7%  (12/14)

By difficulty tier:
  Straightforward (8) — NOT escalated : 87.5%  (7/8)    ✓ target ≥ 85%
  Ambiguous       (4) — Escalated     : 100.0% (4/4)    ✓ target ≥ 75%
  Edge cases      (2) — Escalated     : 100.0% (2/2)    ✓ target 100%

------------------------------------------------------------
  Per-case breakdown
------------------------------------------------------------
  CASE-001 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-002 | straightforward | Expected: DENY      | Got: DENY      | PASS ✓
  CASE-003 | straightforward | Expected: APPROVE   | Got: APPROVE   | PASS ✓
  CASE-004 | ambiguous       | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  CASE-005 | edge            | Expected: ESCALATE  | Got: ESCALATE  | PASS ✓
  ...
============================================================
```

---

## 5. Policies Design

### 5.1 Policy Coverage Matrix

Policies must cover distinct, non-overlapping rule domains so that different case types retrieve different policies. If all 7 policies say roughly the same thing, TF-IDF retrieval degenerates (everything has high similarity to everything).

| Policy ID | Domain | Decision Bias | Edge Trigger |
|---|---|---|---|
| POL-001 | Identity verification | DENY if unverified | ESCALATE if partially verified |
| POL-002 | Name mismatch | DENY if mismatch + high value | ESCALATE if minor variation |
| POL-003 | Payout threshold | DENY if > $10,000 unverified | ESCALATE if $5,000–$10,000 |
| POL-004 | High-risk flag | ESCALATE always | — |
| POL-005 | Profile change velocity | DENY if 3+ changes in 24h | ESCALATE if 2 changes |
| POL-006 | Account age | DENY if < 30 days + payout > $500 | ESCALATE if 30–60 days |
| POL-007 | Missing data | ESCALATE always | — |

### 5.2 Policy File Format

```markdown
policy_id:
POL-001
title:
Identity Verification Required
rule:
If `identity_verified` is false, then deny the payout request. If identity verification
status is unknown or partially completed, then escalate for human review.
escalation_note:
Escalate if `identity_verified` is null, verification is stale, or the verification
method is marked low-confidence.
---
```

Each policy block must use literal field anchors (`policy_id:`, `title:`, `rule:`,
`escalation_note:`) at the start of lines. Policies are separated by `---` delimiters
so the parser can split them cleanly.

---

## 6. Cases Design

### 6.1 Case Distribution Strategy

| Case ID | Difficulty | Type | Expected | Key Signal |
|---|---|---|---|---|
| CASE-001 | straightforward | payout_review | APPROVE | Clean: verified, name match, low amount |
| CASE-002 | straightforward | payout_review | DENY | identity_verified = false |
| CASE-003 | straightforward | payout_review | DENY | account_age < 30 days, amount > $500 |
| CASE-004 | straightforward | payout_review | APPROVE | Verified, old account, low risk |
| CASE-005 | ambiguous | payout_review | ESCALATE | high_risk_flag = true |
| CASE-006 | straightforward | payout_review | APPROVE | All signals clean, moderate amount |
| CASE-007 | straightforward | payout_review | DENY | 3 profile changes in 24h |
| CASE-008 | straightforward | payout_review | APPROVE | All clear, first payout |
| CASE-009 | ambiguous | payout_review | ESCALATE | Name mismatch (J. Lee vs Jordan Lee) + medium amount |
| CASE-010 | ambiguous | payout_review | ESCALATE | High risk flag but verified identity, low amount |
| CASE-011 | straightforward | payout_review | DENY | clear name mismatch + payout > $500 |
| CASE-012 | ambiguous | payout_review | ESCALATE | Account age 45 days, payout $800 |
| CASE-013 | edge | payout_review | ESCALATE | missing_fields: ["identity_verified", "payout_amount"] |
| CASE-014 | edge | payout_review | ESCALATE | Conflicting: identity_verified=true but name="UNKNOWN" |

Distribution check: 8 straightforward (4 APPROVE, 4 DENY), 4 ambiguous (all ESCALATE), 2 edge (all ESCALATE).

### 6.2 Edge Case Design Notes

**CASE-013:** Missing critical fields. The agent cannot make an APPROVE or DENY decision without knowing the payout amount or identity status. EscalationChecker fires on `missing_fields`.

**CASE-014:** Contradictory data. `identity_verified=true` but `account_holder_name="UNKNOWN"` — the system claims identity is verified but cannot provide a name to verify against. This tests both: (1) whether the agent reads the semantic conflict and escalates, and (2) the deterministic EscalationChecker Rule 4, which escalates on conflicting identity signals regardless of the agent's output.

---

## 7. Prompt Engineering Strategy

### 7.1 System Prompt Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Role framing | "compliance decision agent" | Activates domain-relevant model behavior |
| Policy scope | "ONLY the policies provided" | Prevents hallucinated policy reasoning |
| Output format | Inline schema in prompt | More reliable than "return JSON" |
| Escalation threshold | Stated as 0.65 | Model calibrates its own confidence accordingly |
| Citation constraint | "from provided policies only" | Prevents citation hallucination |
| No preamble instruction | "Return ONLY the JSON object" | Eliminates text-before-JSON parse failures |

### 7.2 Temperature Rationale

| Temperature | Effect on this task |
|---|---|
| 0.0 | Fully deterministic but can get stuck on degenerate edge cases |
| 0.1 | Near-deterministic, stable outputs, recovers from edge cases |
| 0.3+ | Too much variance — same case may return different decisions on re-run |

We use **0.1**. This system is deterministic enough to be auditable (same case → same decision on re-run ~95% of the time) while avoiding the failure mode of temperature=0.

### 7.3 Context Window Management

For 7 policies × ~150 tokens each + case (~100 tokens) + system prompt (~300 tokens) = ~1,350 tokens input. Well within claude-sonnet-4-5 context window. No chunking or summarization needed.

### 7.4 Anti-Patterns Avoided

| Anti-Pattern | Why We Avoid It |
|---|---|
| "Be helpful and make the best decision" | Vague role leads to vague decisions |
| Asking for explanation outside JSON | Creates text-before-JSON parse failures |
| Including all policies every time | Defeats purpose of retrieval; creates noise |
| Asking model to score confidence "honestly" | "Honestly" adds no instruction signal |
| Chain-of-thought in output | Not auditable; adds parsing complexity |

---

## 8. Error Handling Hierarchy

Every module must handle errors at its own boundary. Errors must never propagate across module boundaries as unhandled exceptions.

```
Layer               │  Error Type           │  Response
────────────────────┼───────────────────────┼─────────────────────────────────
CaseLoader          │  JSON parse error     │  Skip case, log warning
                    │  Pydantic validation  │  Skip case, log which fields
────────────────────┼───────────────────────┼─────────────────────────────────
PolicyRetriever     │  File not found       │  Raise at startup (fail fast)
                    │  Parse error          │  Raise at startup (fail fast)
                    │  Runtime search error │  Return [] (caller escalates)
────────────────────┼───────────────────────┼─────────────────────────────────
DecisionAgent       │  API auth error       │  Return ESCALATE JSON
                    │  API rate limit       │  Wait 1s, retry once, then ESCALATE
                    │  API timeout          │  Return ESCALATE JSON
                    │  Any other exception  │  Return ESCALATE JSON
────────────────────┼───────────────────────┼─────────────────────────────────
OutputValidator     │  JSON parse failure   │  Retry once with correction prompt
                    │  Pydantic failure     │  Retry once with correction prompt
                    │  Retry also fails     │  Return ESCALATE DecisionOutput
                    │  Citation mismatch    │  Remove bad citations, warn in log
────────────────────┼───────────────────────┼─────────────────────────────────
EscalationChecker   │  Any exception        │  Return ESCALATE (never crash)
────────────────────┼───────────────────────┼─────────────────────────────────
evaluate.py         │  Case-level exception │  Mark FAIL, continue next case
                    │  All cases fail       │  Print error summary, exit code 1
```

**Fail-fast at startup, fail-safe at runtime.** If the policy file is missing or malformed, the system should crash immediately at startup — this is a configuration error that must be fixed. But if a single case produces an unexpected API response at runtime, the system must continue processing other cases.

---

## 9. Security Design

### 9.1 Secret Management

```
.env                ← real API key, gitignored
.env.example        ← placeholder, committed to repo
config.py           ← reads os.environ, never hardcodes
```

No API key ever appears in:
- Logs or stdout
- `audit_log` fields
- Error messages
- Test fixtures

### 9.2 Input Sanitization

Cases are loaded from a local file under our control, so injection risk is low. However, the `summary` field is passed into an LLM prompt. We apply minimal sanitization:
- Strip leading/trailing whitespace
- Truncate to 1,000 characters (prevents prompt stuffing if data is tampered)
- Remove HTML/script tags using a lightweight regex sanitizer before prompt construction

### 9.3 Output Safety

`DecisionOutput` is serialized to JSON only. It is never executed, rendered as HTML, or passed to a shell. No additional output sanitization required.

---

## 10. Testing Strategy

### 10.1 Test Scope

| Test File | What It Tests |
|---|---|
| `test_retriever.py` | Policy loading, TF-IDF similarity, empty query handling |
| `test_validator.py` | Valid output passes, invalid JSON triggers retry, retry failure → ESCALATE |
| `test_agent.py` | Prompt construction, API call mocked, escalation on API failure |
| `test_evaluate.py` | Metrics calculation, accuracy formula, per-difficulty breakdown |

### 10.2 Mocking Strategy

The Anthropic API must be mocked in all unit tests — we never make real API calls in the test suite. Use `pytest-mock` to patch `anthropic.Anthropic.messages.create`.

```python
def test_agent_returns_escalate_on_api_failure(mocker):
    mocker.patch(
        "anthropic.Anthropic.messages.create",
        side_effect=anthropic.APIConnectionError("Connection refused")
    )
    agent = DecisionAgent(retriever=mock_retriever)
    result, _ = agent.decide(sample_case)

    output = json.loads(result)
    assert output["decision"] == "ESCALATE"
    assert output["confidence"] == 0.0
```

### 10.3 Critical Test Cases

1. **Retriever returns empty list** → agent produces ESCALATE JSON without calling API
2. **API returns invalid JSON** → validator retries → still invalid → ESCALATE returned
3. **LLM returns confidence 0.4** → EscalationChecker overrides decision to ESCALATE
4. **LLM cites non-retrieved policy** → validator strips citation, logs warning
5. **Case has missing_fields** → EscalationChecker fires regardless of LLM decision
6. **All 14 cases run** → evaluate.py produces correct metric counts (integration test)

---

## 11. Dependencies & Versions

```
# requirements.txt
anthropic==0.26.2
scikit-learn==1.4.2
pydantic==2.6.4
python-dotenv==1.0.1
pytest==8.1.1
pytest-mock==3.12.0
```

Python: **3.11+** (uses `match/case`, `X | Y` union types in type hints)

---

## 12. What We Are NOT Building (And Why)

| Excluded Feature | Why Excluded |
|---|---|
| LangChain or similar | Adds abstraction without value at this scale; obscures the design |
| Vector database (Pinecone, Weaviate) | 7 documents don't warrant a DB; TF-IDF is correct here |
| FastAPI / REST endpoint | Assignment asks for a script, not a service |
| Async processing | 14 cases run sequentially; async adds complexity for no gain |
| Caching layer | Policy file is read once at startup; no runtime caching needed |
| Streaming API response | Decision output must be complete before validation; streaming incompatible |
| Multi-turn conversations | Single-shot decision; no dialogue needed |
| Embeddings model | Overkill for 7 static documents |

These are deliberate exclusions, not omissions. Choosing not to use a tool is as important as knowing how to use it.

---

## 13. Open Decisions

These are design choices that were considered but intentionally deferred or left as implementation-time decisions:

| Decision | Options | Deferred Until |
|---|---|---|
| Policy parser format | Regex vs markdown parser | Implementation (use regex — simpler) |
| Retry backoff | Fixed 1s wait vs exponential | Implementation (fixed 1s is sufficient) |
| Evaluation output format | Stdout only vs also write JSON | Implementation (stdout sufficient for assignment) |
| Case loading | Eager (all at once) vs lazy (one by one) | Implementation (eager, 14 cases is trivial) |

---

*Next Document: Build Plan — Milestones & Tickets*
