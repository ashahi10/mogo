# Build Plan — Milestones & Tickets
## Project: Orion AI Decision Agent
## Part 1 of 2: Milestones 1–3
**Version:** 1.0  
**Status:** Active  
**Depends On:** PRD v1.0, System Design v1.0  
**Last Updated:** 2025

---

## How to Use This Document

Each milestone represents a self-contained, deliverable unit of work. Complete and verify one milestone fully before starting the next. Each ticket within a milestone has a clear scope, explicit acceptance criteria, dependencies, and a definition of done.

**Ticket ID format:** `M{milestone}-T{ticket}` — e.g., M1-T1 is Milestone 1, Ticket 1.

**Before starting any ticket:** Read the referenced System Design section. Every implementation decision has already been made there. Do not deviate without updating the System Design first.

**Definition of "Done" for a ticket:** All acceptance criteria are met, no TODOs remain in the file, the file is importable without errors, and it is consistent with the Pydantic models in `models.py`.

---

## Milestone Overview

| Milestone | Name | Tickets | Output |
|---|---|---|---|
| M1 | Project Foundation | 4 | Repo skeleton, config, models, dependencies |
| M2 | Data Layer | 3 | policies.md, cases.json, policy parser |
| M3 | Policy Retriever | 3 | retriever.py, query builder, startup validation |
| M4 | Decision Agent | 4 | agent.py, prompt builder, API client wrapper |
| M5 | Validator & Escalation | 4 | validator.py, retry logic, escalation checker |
| M6 | Evaluation & Docs | 5 | evaluate.py, tests, design.md, README |

**Part 1 covers M1 → M3.**  
**Part 2 covers M4 → M6.**

---

# MILESTONE 1: Project Foundation

**Goal:** Establish the complete project skeleton with all configuration, data contracts, and dependencies in place. After M1, every subsequent module can be written in isolation without revisiting structure decisions.

**Completion signal:** Running `python -c "from models import Case, Policy, DecisionOutput; print('OK')"` succeeds. Running `pip install -r requirements.txt` completes without errors.

---

## M1-T1: Initialize Repository Structure

**Title:** Create the full project directory and file skeleton

**Description:**  
Create the complete folder and file structure as defined in Section 8 of the System Design. Every file should be created as an empty placeholder (or with a single comment indicating its purpose) so that imports and references between modules can be established from the beginning. This prevents circular import issues and missing module errors throughout development.

**Acceptance Criteria:**
- The following files exist in the project root:
  - `README.md` (empty placeholder with project title)
  - `design.md` (empty placeholder — filled in M6)
  - `policies.md` (empty placeholder — filled in M2)
  - `cases.json` (empty placeholder containing `[]` — filled in M2)
  - `requirements.txt` (fully populated — see M1-T2)
  - `.env.example` (contains one line: `ANTHROPIC_API_KEY=your_key_here`)
  - `.gitignore` (contains entries for `.env`, `__pycache__`, `.pytest_cache`, `*.pyc`, `.DS_Store`)
  - `config.py` (fully populated — see M1-T3)
  - `models.py` (fully populated — see M1-T4)
  - `retriever.py` (empty placeholder with module docstring)
  - `agent.py` (empty placeholder with module docstring)
  - `validator.py` (empty placeholder with module docstring)
  - `evaluate.py` (empty placeholder with module docstring)
- The `tests/` directory exists and contains:
  - `__init__.py` (empty)
  - `test_retriever.py` (empty placeholder)
  - `test_validator.py` (empty placeholder)
  - `test_agent.py` (empty placeholder)
  - `test_evaluate.py` (empty placeholder)
- No file contains any implementation logic yet (except `config.py` and `models.py` which are completed in M1-T3 and M1-T4)

**Dependencies:** None — this is the first ticket.

**System Design Reference:** Section 8 (File Structure)

**Implementation Notes:**
- The `.env` file itself is NOT created — only `.env.example`. The developer creates `.env` manually and populates it with a real API key.
- `cases.json` must contain a valid empty JSON array `[]`, not be blank — a blank file will cause a JSON parse error when the file is first read.
- Module docstrings in placeholder files should state the module's single responsibility as described in the System Design. This gives the AI coding tool context when it opens the file.

**Definition of Done:**
- All files and directories exist as listed above
- `.gitignore` contains `.env` entry (verified: `cat .gitignore | grep .env` returns a result)
- `python -c "import config; import models"` runs without error

---

## M1-T2: Pin All Dependencies in requirements.txt

**Title:** Create fully pinned requirements.txt with all project dependencies

**Description:**  
Populate `requirements.txt` with the exact dependency list and pinned versions as specified in Section 11 of the System Design. Pinning exact versions is mandatory for this project — it ensures reproducibility and prevents the evaluator from encountering version mismatch errors when they run the project.

**Acceptance Criteria:**
- `requirements.txt` contains all of the following packages at the specified versions:
  - `anthropic==0.26.2`
  - `scikit-learn==1.4.2`
  - `pydantic==2.6.4`
  - `python-dotenv==1.0.1`
  - `pytest==8.1.1`
  - `pytest-mock==3.12.0`
- No additional packages appear in `requirements.txt` beyond these six
- Running `pip install -r requirements.txt` completes without dependency conflict errors on Python 3.11
- The file uses `==` (exact pin) for all packages — not `>=` or `~=`

**Dependencies:** M1-T1

**System Design Reference:** Section 11 (Dependencies & Versions)

**Implementation Notes:**
- `scikit-learn` will pull in `numpy` and `scipy` as transitive dependencies — these do not need to appear in `requirements.txt` since they are managed automatically. Only direct project dependencies are listed.
- `python-dotenv` is a direct dependency because `config.py` uses it. Do not omit it assuming the developer will have it installed globally.
- Do not include `anthropic[extras]` or any extras notation — the base package is sufficient.

**Definition of Done:**
- `pip install -r requirements.txt` completes cleanly on a fresh Python 3.11 environment
- `python -c "import anthropic; import sklearn; import pydantic; import dotenv; import pytest"` runs without ImportError

---

## M1-T3: Implement config.py

**Title:** Create the centralized configuration module with all system constants

**Description:**  
Implement `config.py` as the single source of truth for all tunable parameters in the system. Every value that could reasonably need adjustment — model name, thresholds, file paths, toggle flags — must live here. No other module may define its own constants. Any other module that needs a constant imports it from `config.py`.

This module also handles environment variable loading. The Anthropic API key is loaded here and exposed as a module-level constant. All other modules that need the API key import it from `config.py`, not from `os.environ` directly.

**Acceptance Criteria:**
- `config.py` defines the following constants with the specified values:
  - `MODEL_NAME = "claude-sonnet-4-5"` — the Anthropic model to use
  - `MAX_TOKENS = 1024` — maximum tokens for LLM response
  - `TEMPERATURE = 0.1` — LLM sampling temperature
  - `RETRIEVAL_TOP_K = 3` — number of policies returned by retriever
  - `CONFIDENCE_THRESHOLD = 0.65` — below this, EscalationChecker overrides to ESCALATE
  - `MIN_POLICY_CITATIONS = 1` — minimum citations required in every valid output
  - `CASES_FILE = "cases.json"` — path to case dataset
  - `POLICIES_FILE = "policies.md"` — path to policy document
  - `ESCALATE_ON_MISSING_FIELDS = True` — boolean flag for escalation rule
  - `ESCALATE_ON_RETRIEVAL_FAILURE = True` — boolean flag for escalation rule
  - `ESCALATE_ON_VALIDATION_FAILURE = True` — boolean flag for escalation rule
- `config.py` calls `load_dotenv()` at module load time so `.env` is populated before any constant is read
- `ANTHROPIC_API_KEY` is read from the environment using `os.environ.get("ANTHROPIC_API_KEY")` and stored as a module-level constant
- If `ANTHROPIC_API_KEY` is not set in the environment, `config.py` prints a clear warning message but does NOT raise an exception at import time (the API client will raise at call time, which is the correct place to fail)
- All constants have an inline comment explaining their purpose and acceptable value range where relevant

**Dependencies:** M1-T1, M1-T2

**System Design Reference:** Section 4.1 (config.py)

**Implementation Notes:**
- The `load_dotenv()` call must happen before any `os.environ.get()` calls in the same file. Place it immediately after the imports, before any constant definitions.
- `TEMPERATURE = 0.1`, not `0.0`. This is a deliberate design decision documented in Section 7.2 of the System Design. Do not change it.
- Constants must use uppercase names (Python convention for module-level constants). No camelCase or lowercase constants in this file.
- Do not add any logic, classes, or functions to `config.py`. It is a flat configuration file only.

**Definition of Done:**
- `python -c "import config; print(config.MODEL_NAME)"` prints `claude-sonnet-4-5`
- `python -c "import config; print(config.CONFIDENCE_THRESHOLD)"` prints `0.65`
- File contains no functions, classes, or conditional logic — only imports and constant assignments

---

## M1-T4: Implement models.py

**Title:** Create all Pydantic v2 data models with validators

**Description:**  
Implement `models.py` with all Pydantic v2 data models that define the system's data contracts. Every piece of data that passes between modules must be an instance of one of these models — never a raw dict, never a bare string (except the raw LLM response before parsing). This is the most important file in the project from a reliability standpoint. If models are correct and validators are thorough, an entire class of runtime bugs becomes impossible.

**Acceptance Criteria:**

**Input models — `CaseAttributes`:**
- Fields: `case_type` (str, required), `payout_amount` (Optional float, default None), `identity_verified` (Optional bool, default None), `verified_name` (Optional str, default None), `account_holder_name` (Optional str, default None), `recent_profile_changes` (Optional int, default None), `high_risk_flag` (Optional bool, default None), `account_age_days` (Optional int, default None), `missing_fields` (list of str, default empty list), `transaction_velocity` (Optional int, default None)
- `payout_amount` must be non-negative if provided — a field validator raises `ValueError` if the value is below 0
- `account_age_days` must be non-negative if provided
- `recent_profile_changes` must be non-negative if provided

**Input models — `Case`:**
- Fields: `case_id` (str, required), `summary` (str, required), `attributes` (CaseAttributes, required), `expected_decision` (Literal["APPROVE", "DENY", "ESCALATE"], required), `difficulty` (Literal["straightforward", "ambiguous", "edge"], required)
- `summary` is sanitized to remove HTML/script tags, then trimmed of leading/trailing whitespace and truncated to 1,000 characters using a field validator (per System Design Section 9.2 on input sanitization)
- `case_id` must match pattern `CASE-\d{3}` — a field validator raises `ValueError` if not

**Input models — `Policy`:**
- Fields: `policy_id` (str, required), `title` (str, required), `rule` (str, required), `escalation_note` (Optional str, default None), `similarity_score` (float, default 0.0)
- `policy_id` must match pattern `POL-\d{3}` — a field validator raises `ValueError` if not
- `similarity_score` must be in range 0.0–1.0 inclusive

**Output models — `PolicyCitation`:**
- Fields: `policy_id` (str, required), `reason` (str, required)
- `reason` must not be empty or whitespace-only — a field validator raises `ValueError` if so
- `policy_id` must match pattern `POL-\d{3}`

**Output models — `AuditLog`:**
- Fields: `retrieved_policies` (list of str, required), `retrieval_score` (float, required), `timestamp` (str, required), `retry_attempted` (bool, required), `error_detail` (Optional str, default None)
- `timestamp` must be a non-empty string — no format validation needed (populated programmatically)
- `retrieval_score` must be in range 0.0–1.0 inclusive

**Output models — `DecisionOutput`:**
- Fields: `case_id` (str, required), `decision` (Literal["APPROVE", "DENY", "ESCALATE"], required), `confidence` (float, required), `policy_citations` (list of PolicyCitation, required), `audit_log` (AuditLog, required)
- `confidence` must be in range 0.0–1.0 inclusive — a field validator raises `ValueError` if not
- `policy_citations` must contain at least one item — a field validator raises `ValueError` if the list is empty
- `case_id` must match pattern `CASE-\d{3}`

**Additional model requirements:**
- All models use `model_config = ConfigDict(frozen=False)` — outputs need to be mutable for the escalation checker's `model_copy(update=...)` operation
- All models use `model_config` with `extra="forbid"` — any unexpected field in the data causes a validation error rather than silent ignoring. This catches LLM responses that include extra fields.
- All field validators use the `@field_validator` decorator (Pydantic v2 syntax, not v1 `@validator`)

**Dependencies:** M1-T1, M1-T2

**System Design Reference:** Section 4.2 (models.py — Data Contracts)

**Implementation Notes:**
- Import order in `models.py`: standard library (`re`, `typing`), then `pydantic` imports, then `config` imports. No other imports needed.
- The `extra="forbid"` configuration on `DecisionOutput` is specifically important because the LLM sometimes adds an `"explanation"` or `"reasoning"` field to its JSON. With `extra="forbid"`, this immediately triggers validation failure and the retry path, rather than silently passing through.
- `model_copy(update=...)` is the Pydantic v2 replacement for `.copy(update=...)`. Ensure the model is not frozen, otherwise `model_copy` will raise.
- The `CaseAttributes.missing_fields` field defaults to an empty list `[]`. In Pydantic v2, mutable defaults must use `default_factory=list`. Using `default=[]` directly is incorrect and will raise a warning.
- All `Optional[X]` fields in Pydantic v2 must be typed as `Optional[X] = None` — not just `Optional[X]`. The `= None` is required for the field to actually be optional.

**Definition of Done:**
- `python -c "from models import Case, Policy, DecisionOutput, PolicyCitation, AuditLog, CaseAttributes; print('OK')"` runs without error
- Instantiating a `DecisionOutput` with an empty `policy_citations` list raises a `ValidationError`
- Instantiating a `DecisionOutput` with `confidence = 1.5` raises a `ValidationError`
- Instantiating a `Case` with `expected_decision = "MAYBE"` raises a `ValidationError`
- Instantiating a `DecisionOutput` with an extra field `"explanation": "some text"` raises a `ValidationError`

---

# MILESTONE 2: Data Layer

**Goal:** Create all static data that the system operates on — the policy rules and the case dataset — plus the parser that loads policies from markdown into `Policy` model instances. After M2, the retriever and agent have everything they need to operate.

**Completion signal:** Running `python -c "from retriever import load_policies; p = load_policies('policies.md'); print(len(p), 'policies loaded')"` prints `7 policies loaded`.

---

## M2-T1: Write policies.md

**Title:** Author the 7 fintech policy documents in structured markdown format

**Description:**  
Write the complete `policies.md` file containing all 7 policy rules the decision agent will use. The policies must be realistic, distinct from each other, written in clear conditional language, and structured in a consistent format that the parser in M2-T3 can reliably extract.

The quality of policies directly determines the quality of the agent's decisions. Policies that overlap in meaning will cause retrieval to return redundant results. Policies that are vague will cause the LLM to produce low-confidence decisions. Policies must be specific, non-overlapping, and grounded in realistic fintech compliance scenarios.

**Acceptance Criteria:**

**Structure requirements:**
- Each policy block is separated from the next by a line containing only `---`
- Each policy block contains exactly these four labeled fields, in this order:
  - `policy_id:` on its own line, followed by the ID value
  - `title:` on its own line, followed by the title
  - `rule:` on its own line, followed by 1–3 sentences stating the condition and required action
  - `escalation_note:` on its own line, followed by the edge case that triggers ESCALATE instead of a binary decision
- No policy block is missing any of these four fields
- The file ends with a final `---` separator

**Content requirements (one policy per domain):**

Policy 1 — Identity Verification:
- `policy_id: POL-001`
- Rule covers: if `identity_verified` is false, the case must be denied. If identity status is unknown (null/missing), the case must be escalated.
- Escalation note: covers cases where verification status is present but stale, ambiguous, or flagged as low-confidence method

Policy 2 — Name Mismatch:
- `policy_id: POL-002`
- Rule covers: if the `account_holder_name` does not match `verified_name` and the payout amount exceeds $500, deny. Exact match required for payouts above $500.
- Escalation note: covers minor name variations (initials, abbreviations, hyphenated names) where intent is unclear

Policy 3 — Payout Amount Threshold:
- `policy_id: POL-003`
- Rule covers: payouts exceeding $10,000 require additional human review regardless of verification status. Payouts of $5,000–$10,000 require escalation if any other risk signal is present.
- Escalation note: covers borderline amounts where rounding or partial payment structures are ambiguous

Policy 4 — High-Risk Account Flag:
- `policy_id: POL-004`
- Rule covers: any case where `high_risk_flag` is true must be escalated for human review. The flag cannot be overridden by other passing signals. Even a fully verified, name-matched account must be escalated if flagged.
- Escalation note: this rule has no DENY path — all high-risk cases go to ESCALATE, never direct DENY

Policy 5 — Profile Change Velocity:
- `policy_id: POL-005`
- Rule covers: if `recent_profile_changes` is 3 or more within 24 hours, deny the payout. This velocity indicates potential account takeover.
- Escalation note: if `recent_profile_changes` is exactly 2, escalate rather than deny — two changes may indicate legitimate activity

Policy 6 — New Account Restriction:
- `policy_id: POL-006`
- Rule covers: accounts with `account_age_days` less than 30 days may not process payouts exceeding $500. Deny if both conditions are met.
- Escalation note: accounts aged 30–60 days with payouts between $500 and $2,000 should be escalated rather than denied

Policy 7 — Missing Critical Data:
- `policy_id: POL-007`
- Rule covers: if `missing_fields` contains any of `identity_verified`, `payout_amount`, `account_holder_name`, or `verified_name`, the case cannot be decided and must be escalated.
- Escalation note: if non-critical fields are missing (e.g., `transaction_velocity`) but all four critical fields are present, the case may proceed to a decision with reduced confidence

**Additional content requirements:**
- Every rule is written in the conditional format: "If [condition], then [action]"
- No two policies share the same primary condition — each covers a distinct signal
- Language is formal and precise — written as a compliance document, not casual prose
- No policy mentions a specific customer name, case ID, or date

**Dependencies:** M1-T1

**System Design Reference:** Section 5 (Policies Design), Section 5.1 (Policy Coverage Matrix), Section 5.2 (Policy File Format)

**Implementation Notes:**
- The field labels (`policy_id:`, `title:`, `rule:`, `escalation_note:`) must appear at the start of their respective lines with no leading whitespace. The parser in M2-T3 uses these as parsing anchors.
- Rule text that spans multiple sentences is fine and expected. The parser reads everything between one label and the next as the field value.
- The `---` separator must appear on its own line with no surrounding whitespace. A `---` inside a sentence would not be treated as a separator.
- Write the escalation notes carefully — they are the source of the "ambiguous" case design. CASE-009 through CASE-012 in `cases.json` are designed to trigger these exact escalation notes.

**Definition of Done:**
- `policies.md` contains exactly 7 policy blocks
- Each block has all four required fields
- Each `policy_id` is unique and follows the `POL-00X` pattern
- No two policies have the same primary condition
- The file can be read and parsed by the function in M2-T3 without errors

---

## M2-T2: Write cases.json

**Title:** Create the 14-case test dataset with ground truth labels

**Description:**  
Populate `cases.json` with all 14 test cases distributed across three difficulty tiers as defined in Section 6 of the System Design. The cases must be designed to comprehensively test the agent's ability to handle the full range of policy conditions — clear signals, ambiguous overlaps, and edge cases with structural problems.

The `expected_decision` field on each case is the ground truth label used by `evaluate.py`. These labels must be logically consistent with the policies in `policies.md`. An evaluator reading a case should be able to trace the expected decision back to a specific policy rule.

**Acceptance Criteria:**

**File structure:**
- `cases.json` is a valid JSON array containing exactly 14 case objects
- Each case object contains: `case_id`, `summary`, `attributes`, `expected_decision`, `difficulty`
- All `case_id` values are unique and follow the `CASE-XXX` format (CASE-001 through CASE-014)
- All `expected_decision` values are one of: `"APPROVE"`, `"DENY"`, `"ESCALATE"`
- All `difficulty` values are one of: `"straightforward"`, `"ambiguous"`, `"edge"`

**Distribution requirements:**
- Exactly 8 cases have `difficulty: "straightforward"` (4 APPROVE, 4 DENY)
- Exactly 4 cases have `difficulty: "ambiguous"` (all 4 expected ESCALATE)
- Exactly 2 cases have `difficulty: "edge"` (both expected ESCALATE)

**Straightforward cases — design rules:**
- Each APPROVE case must have: `identity_verified: true`, matching names, no high-risk flag, `account_age_days` > 60, `recent_profile_changes` ≤ 1, `missing_fields: []`, and a payout amount comfortably below all thresholds
- Each DENY case must clearly trigger exactly one policy rule (identity false, or name mismatch + amount > $500, or account age < 30 days + amount > $500, or profile changes ≥ 3) — not multiple rules simultaneously. Single-signal denials are easiest for the agent and serve as baseline tests.
- No straightforward case should have any ambiguous signals — every attribute should clearly point toward one outcome

**Ambiguous cases — design rules:**
- CASE-005: `high_risk_flag: true` with otherwise clean attributes. Per POL-004, high-risk flag is an absolute escalation trigger. Expected: ESCALATE.
- CASE-009: Name variation (abbreviated first name vs full first name) with `payout_amount` of $1,200. Both POL-002 (name mismatch) and a clean verification status apply. The name is arguably a match (same person) or not (different string). Expected: ESCALATE.
- CASE-010: `high_risk_flag: true` but `identity_verified: true`, name matches, account is old, payout is low ($200). High risk flag forces ESCALATE per POL-004, but everything else is clean. Tests whether agent correctly applies POL-004 as absolute.
- CASE-012: `account_age_days: 45`, `payout_amount: 950` — sits in the escalation zone of POL-006 (30–60 days, $500–$2,000). No other risk signals. Expected: ESCALATE.

**Case-specific correction to preserve target distribution:**
- CASE-011 is a straightforward DENY case (not ambiguous): define it as a clear `verified_name` vs `account_holder_name` mismatch with `payout_amount > $500` so POL-002 applies deterministically.

**Edge cases — design rules:**
- CASE-013: `missing_fields: ["identity_verified", "payout_amount"]`. These are two of the four critical fields listed in POL-007. No decision is possible. Other attributes may be present and clean — the missing fields must be the only trigger. Expected: ESCALATE.
- CASE-014: `identity_verified: true` but `account_holder_name: "UNKNOWN"` and `verified_name: "Sarah Chen"`. The system claims identity is verified but cannot provide a consistent name — a structural contradiction. `high_risk_flag: false`, `missing_fields: []`. This is valid JSON but logically contradictory data. Expected: ESCALATE.

**Attribute requirements:**
- Every case must include all fields defined in `CaseAttributes` — either with a value or explicitly set to `null` for optional fields
- `missing_fields` must only list fields that are actually null/absent in the attributes object. If `payout_amount` is in `missing_fields`, its value in the attributes object must be `null`.
- Payout amounts for APPROVE cases must be realistic: $100–$2,000 range
- Payout amounts for high-value DENY cases must clearly exceed relevant thresholds
- Summaries must read as natural English descriptions, as if written by a human compliance operator reviewing the case — not as structured data descriptions

**Dependencies:** M2-T1 (policies must exist before designing case signals)

**System Design Reference:** Section 6 (Cases Design), Section 6.1 (Case Distribution Strategy), Section 6.2 (Edge Case Design Notes)

**Implementation Notes:**
- Write the summary for each case first, then populate the attributes to match the summary. Summaries that contradict the attributes confuse the LLM and produce unpredictable results.
- Ambiguous cases should have summaries that reflect the ambiguity — a human reading the summary should also feel uncertain about the correct decision.
- Edge case summaries should describe the structural problem directly: "Customer's account shows identity as verified but no name is recorded on file."
- Do not use the names "Jordan Lee" or "J. Smith" from the assignment's example case — use different names to demonstrate original design.
- Payout amounts for straightforward DENY cases should be unambiguously over thresholds: e.g., if the new account threshold is > $500, use $1,500 (not $501).
- Run a manual consistency check before finalizing: for each case, read the summary, look at the attributes, identify which policies apply, and confirm the `expected_decision` matches the policy outcome.

**Definition of Done:**
- `python -c "import json; cases = json.load(open('cases.json')); print(len(cases), 'cases')"` prints `14 cases`
- Exactly 8 straightforward, 4 ambiguous, 2 edge cases
- All 14 cases parse successfully against the `Case` Pydantic model
- Manual review confirms every `expected_decision` is traceable to a specific policy

---

## M2-T3: Implement Policy Parser in retriever.py

**Title:** Write the policy parser that loads policies.md into Policy model instances

**Description:**  
Implement the `load_policies(path: str) -> list[Policy]` function in `retriever.py`. This function reads `policies.md`, parses each policy block into structured data, and returns a list of validated `Policy` model instances. This function is called once at startup by the `PolicyRetriever` class — it is not called on every request.

This ticket implements only the loading and parsing logic. The `PolicyRetriever` class and TF-IDF index construction are implemented in M3.

**Acceptance Criteria:**
- `load_policies(path)` accepts a file path string and returns `list[Policy]`
- The function parses policy blocks separated by `---` delimiters
- For each block, the function extracts the values of `policy_id`, `title`, `rule`, and `escalation_note` using the field labels as parsing anchors
- The extracted fields are used to instantiate a `Policy` model — if Pydantic validation fails for a block, a descriptive error is raised indicating which block failed and why
- `escalation_note` is treated as optional — if a block does not contain the `escalation_note:` label, the field is set to `None`
- `similarity_score` is set to `0.0` for all policies loaded from file — it is populated later by the retriever
- If the file at `path` does not exist, the function raises `FileNotFoundError` with a message indicating the expected path
- If the file is found but contains fewer than 5 policy blocks, the function raises `ValueError` with a message indicating the expected minimum
- The function does not log, print, or produce any output on successful load — it returns the list silently

**Parsing logic requirements:**
- Split the file content on `\n---\n` to get individual policy blocks
- Strip each block of leading and trailing whitespace before processing
- Skip any block that is empty after stripping (handles leading/trailing `---` in the file)
- For each non-empty block, extract field values by finding the label (e.g., `rule:`) and reading all text until the next label or end of block
- Field values must be stripped of leading/trailing whitespace after extraction
- Parsing must be case-insensitive for field labels — `Policy_ID:` and `policy_id:` both work

**Dependencies:** M1-T4 (Policy model must exist), M2-T1 (policies.md must exist)

**System Design Reference:** Section 4.3 (PolicyRetriever Design), Section 5.2 (Policy File Format)

**Implementation Notes:**
- The parsing approach should treat each policy block as a small document with labeled sections. The pattern is: find a label, consume text until the next label is found or the block ends.
- A reliable approach is to use `re.split` with a pattern that matches any of the four field labels as delimiters, then pair the label with the following text.
- `escalation_note` is the last field in each block. Its value runs to the end of the block. Handle this as a special case if using a label-detection approach.
- Do not use a YAML or TOML parser — the policy file format is custom markdown, not a standard format. String parsing is correct here.
- The function must be importable on its own without side effects. It should not call itself or instantiate any classes at import time.

**Definition of Done:**
- `python -c "from retriever import load_policies; p = load_policies('policies.md'); print(len(p))"` prints `7`
- Each returned object is a valid `Policy` instance (confirmed by checking `isinstance(p[0], Policy)`)
- Calling `load_policies('nonexistent.md')` raises `FileNotFoundError`
- All 7 returned policies have `similarity_score == 0.0`
- All 7 returned policies have non-empty `policy_id`, `title`, and `rule` fields

---

# MILESTONE 3: Policy Retriever

**Goal:** Build the complete `PolicyRetriever` class that wraps the parser, TF-IDF vectorizer, and similarity search. By the end of M3, the retriever is fully functional and independently testable. The agent in M4 will use it directly.

**Completion signal:** Running a standalone retriever test — creating a `PolicyRetriever`, calling `.search("unverified identity payout request")`, and confirming the top result is `POL-001` — passes.

---

## M3-T1: Implement PolicyRetriever Class

**Title:** Build the TF-IDF-based PolicyRetriever with index construction at init

**Description:**  
Implement the `PolicyRetriever` class in `retriever.py`. This class is responsible for: loading policies at initialization, building a TF-IDF index from the policy corpus, and exposing a `search()` method that returns the top-k most similar policies for a given query. The class is instantiated once per application run, not once per case.

**Acceptance Criteria:**

**Class initialization:**
- `PolicyRetriever.__init__(self, policies_path: str)` accepts the path to `policies.md`
- `__init__` calls `load_policies(policies_path)` and stores the result as `self.policies`
- `__init__` raises `FileNotFoundError` (propagated from `load_policies`) if the file does not exist — this is a startup failure, not a runtime failure
- `__init__` constructs a `TfidfVectorizer` with `ngram_range=(1, 2)`, `stop_words="english"`, `max_features=500`
- `__init__` builds the TF-IDF corpus by concatenating each policy's `title`, `rule`, and `escalation_note` (if present) into a single string per policy, separated by spaces
- `__init__` calls `vectorizer.fit_transform(corpus)` and stores the result as `self.policy_matrix`
- After `__init__` completes, the retriever is ready to accept search queries — no lazy initialization

**Search method:**
- `PolicyRetriever.search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> list[Policy]` is the public interface
- The method transforms the query string using `self.vectorizer.transform([query])` — note: `transform`, not `fit_transform` — the vectorizer was already fitted on the policy corpus
- The method computes cosine similarity between the query vector and `self.policy_matrix`
- The method returns the top-k policies sorted by descending similarity score
- The method filters out policies with a similarity score of exactly 0.0 — only policies that share at least one term with the query are returned
- Each returned `Policy` object has its `similarity_score` set to the computed similarity value (float, rounded to 4 decimal places)
- The returned list may be shorter than `top_k` if fewer than `top_k` policies have a non-zero similarity score
- If the query produces zero non-zero matches, the method returns an empty list `[]`
- If any exception occurs during the search (vectorizer error, numpy error, etc.), the method catches it, logs the error message to stderr, and returns an empty list `[]` — it never raises

**Dependencies:** M1-T3 (config constants), M1-T4 (Policy model), M2-T3 (load_policies function), M1-T2 (scikit-learn installed)

**System Design Reference:** Section 4.3 (PolicyRetriever Design), Section 4.3.1 (Why TF-IDF), Section 4.3.2 (PolicyRetriever Design)

**Implementation Notes:**
- The `cosine_similarity` function from `sklearn.metrics.pairwise` takes two matrices and returns a 2D array. When called with a single query vector and the policy matrix, it returns shape `(1, num_policies)`. Access the scores with `[0]` to get a 1D array.
- `scores.argsort()[::-1]` sorts indices from highest to lowest score. Take the first `top_k` of these.
- The `model_copy()` call on each returned policy is important — do not mutate the `self.policies` list directly when setting `similarity_score`. Return copies with the updated score.
- `ngram_range=(1, 2)` means unigrams and bigrams are both indexed. This is important for policy language where compound terms like "high risk" or "name mismatch" carry meaning as a pair.
- `max_features=500` is a safety cap — with only 7 documents, the actual vocabulary will be much smaller, so this cap won't reduce coverage. It protects against edge cases where corpus text is unusually long.
- Do not import `numpy` explicitly — use the array operations via scikit-learn's return values. If numpy-specific operations are needed, import it.

**Definition of Done:**
- `PolicyRetriever('policies.md')` initializes without error
- `retriever.search("unverified identity")` returns a non-empty list with `POL-001` as the first result
- `retriever.search("high risk account")` returns a list containing `POL-004`
- `retriever.search("xyzabc123 nonsense query with no matching terms")` returns an empty list `[]`
- Each returned policy has `0.0 < similarity_score <= 1.0`

---

## M3-T2: Implement build_retrieval_query Function

**Title:** Write the query enrichment function that constructs TF-IDF queries from case data

**Description:**  
Implement `build_retrieval_query(case: Case) -> str` as a standalone function in `retriever.py`. This function takes a `Case` object and constructs an enriched query string for the TF-IDF retriever by combining the natural language summary with key structured signals extracted from `case.attributes`.

The purpose of this function is to bridge the gap between structured case data and the text-based TF-IDF index. Without enrichment, a case summary like "Customer requests payout" would retrieve poor results because it lacks the specific terminology used in the policies. With enrichment, the query contains phrases like "high risk flagged account" and "name mismatch identity discrepancy" that directly match policy language.

**Acceptance Criteria:**
- `build_retrieval_query(case: Case) -> str` accepts a `Case` model and returns a non-empty string
- The returned string always begins with `case.summary` as its first component
- The following conditional enrichments are appended (in this order) when conditions are met:
  - If `attributes.high_risk_flag` is `True`: append `"high risk flagged account"`
  - If `attributes.missing_fields` is non-empty: append `"missing fields: "` followed by the comma-joined field names
  - If `attributes.identity_verified` is `False`: append `"identity not verified unverified account"`
  - If `attributes.identity_verified` is `None`: append `"identity verification status unknown missing"`
  - If both `verified_name` and `account_holder_name` are present and their lowercase stripped values do not match: append `"name mismatch identity discrepancy account holder mismatch"`
  - If `recent_profile_changes` is not None and `recent_profile_changes >= 2`: append `"multiple recent profile changes velocity suspicious activity"`
  - If `payout_amount` is not None and `payout_amount > 5000`: append `"large payout high value transaction threshold"`
  - If `account_age_days` is not None and `account_age_days < 60`: append `"new account age restriction recently opened"`
- All appended strings are joined with a single space
- The function never raises — if any attribute access fails (unexpected None), that enrichment is skipped silently

**Dependencies:** M1-T4 (Case model)

**System Design Reference:** Section 4.3.3 (Query Construction)

**Implementation Notes:**
- This function is pure — it takes data in and returns a string. No side effects, no I/O, no state.
- The name-matching comparison must handle common real-world variations: "J. Smith" and "Jordan Smith" should be flagged as a mismatch. A simple `!=` string comparison after lowercasing and stripping is sufficient. Do not implement fuzzy matching here — that complexity belongs in a future iteration (noted in design.md).
- The enrichment phrases are chosen to match the vocabulary in `policies.md`. If the policy language uses the phrase "account takeover," that phrase or its key terms should appear in the enrichment for the velocity trigger.
- The function must handle the case where `attributes.identity_verified` is `None` separately from `False`. `None` means the field is missing (unknown). `False` means it was checked and failed. These have different policy implications.
- Appending phrases for `account_age_days < 60` is intentionally broader than the 30-day threshold in POL-006. We want to retrieve POL-006 for both the deny zone (< 30 days) and the escalation zone (30–60 days). Retrieval should err on the side of over-inclusion; the LLM will apply the precise threshold.

**Definition of Done:**
- `build_retrieval_query(case_with_high_risk_true)` returns a string containing `"high risk flagged account"`
- `build_retrieval_query(case_with_name_mismatch)` returns a string containing `"name mismatch"`
- `build_retrieval_query(case_with_missing_fields)` returns a string containing `"missing fields"`
- `build_retrieval_query(clean_case)` returns exactly `case.summary` with no appended enrichments
- The function never raises when called with a case that has all optional attributes set to `None`

---

## M3-T3: Validate Retriever Integration and Write Startup Check

**Title:** Add startup validation and wire retriever components together

**Description:**  
Add a `validate_setup()` function to `retriever.py` that verifies the complete data layer is ready before the application starts processing cases. Additionally, confirm that `build_retrieval_query` and `PolicyRetriever.search()` work correctly as an integrated pair on representative inputs.

This ticket does not add new components — it adds a safety check that runs at startup and ensures the retriever + query builder produce sensible results on known inputs.

**Acceptance Criteria:**

**`validate_setup(policies_path: str, cases_path: str) -> None` function:**
- Attempts to load policies from `policies_path` using `load_policies()`
- Verifies at least 5 policies were loaded
- Attempts to parse `cases_path` as a JSON array
- Verifies at least 10 cases were found
- Verifies the `cases_path` file is valid JSON (no parse errors)
- If any check fails, raises `RuntimeError` with a clear message describing what failed and what was expected
- If all checks pass, prints a single line to stdout: `"Setup validated: {n} policies, {m} cases loaded."` and returns

**PolicyRetriever integration requirements (verified by tests in M6, but the code must support them now):**
- `PolicyRetriever.search()` called with the result of `build_retrieval_query()` on a case must return at least one policy for any case that has a non-empty summary
- The top-returned policy for a case clearly involving identity verification (`identity_verified: false`) must have `policy_id == "POL-001"` — if this fails, it indicates the policies.md vocabulary does not align with the query enrichment vocabulary (a content problem, not a code problem)

**`retriever.py` module-level usage:**
- When `retriever.py` is run directly as a script (`python retriever.py`), it must execute `validate_setup(POLICIES_FILE, CASES_FILE)` and print the result. This allows quick manual verification without writing a separate script.
- This behavior is gated behind `if __name__ == "__main__":` and does not run on import

**Dependencies:** M3-T1, M3-T2, M2-T1, M2-T2

**System Design Reference:** Section 8 (Error Handling Hierarchy — CaseLoader and PolicyRetriever rows), Section 4.3 (PolicyRetriever Design)

**Implementation Notes:**
- `validate_setup` is a defensive programming tool, not a testing tool. It checks configuration (files exist, have content) rather than behavior (results are correct). Behavioral tests belong in `tests/`.
- The JSON validation of `cases_path` in `validate_setup` should use `json.load()` — if this raises, the error message should tell the developer exactly what is wrong with the JSON syntax.
- If the identity verification retrieval check described above fails (top result is not POL-001), this is a signal to revisit either the `escalation_note` content in `policies.md` or the enrichment phrases in `build_retrieval_query`. Document this explicitly in a comment in the test.
- `validate_setup` should not instantiate a `PolicyRetriever` — it only checks that the files are readable and valid. PolicyRetriever is instantiated in `agent.py` at application startup.

**Definition of Done:**
- `python retriever.py` prints `"Setup validated: 7 policies, 14 cases loaded."` and exits cleanly
- `validate_setup('nonexistent.md', 'cases.json')` raises `RuntimeError`
- `validate_setup('policies.md', 'cases.json')` runs without error
- The function is importable without side effects (`from retriever import validate_setup` does not execute anything)

---

*End of Part 1 — Milestones 1 through 3*  
*Part 2 covers Milestones 4 through 6: Decision Agent, Validator & Escalation, Evaluation & Docs*
