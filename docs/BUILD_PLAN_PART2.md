# Build Plan — Milestones & Tickets
## Project: Orion AI Decision Agent
## Part 2 of 2: Milestones 4–6
**Version:** 1.0
**Status:** Active
**Depends On:** PRD v1.0, System Design v1.0, Build Plan Part 1
**Last Updated:** 2025

---

## Reminder: How to Use This Document

Complete each milestone fully before starting the next. Every ticket references a specific System Design section — read it before implementing. The definition of done for each ticket is a runnable verification command or an explicit observable outcome, not a subjective judgment call.

**At this point in the build, Milestones 1–3 are complete.** The following are confirmed working before starting M4:
- All Pydantic models import cleanly from `models.py`
- `config.py` loads API key from `.env` without error
- `policies.md` contains 7 parsed, validated policies
- `cases.json` contains 14 cases that all validate against the `Case` model
- `PolicyRetriever('policies.md').search("unverified identity payout")` returns at least one result with `POL-001` at the top
- `python retriever.py` prints setup validation success

---

# MILESTONE 4: Decision Agent

**Goal:** Build the complete `DecisionAgent` class in `agent.py` — including the system prompt, user message builder, API client wrapper, and the full decision pipeline for a single case. By the end of M4, calling `agent.decide(case)` on any valid `Case` object returns a raw JSON string and a list of retrieved policies. The validator in M5 handles everything after that.

**Completion signal:** Running `python agent.py` in the project root processes one hardcoded sample case (CASE-001), prints the raw JSON response from the API, and exits cleanly. No crashes. No empty output.

---

## M4-T1: Write the System Prompt and User Message Builder

**Title:** Define the LLM prompt constants and implement the user message construction function

**Description:**
Implement the prompt layer in `agent.py`. This consists of two parts: a module-level string constant `SYSTEM_PROMPT` that defines the agent's role, output contract, and escalation rules, and a function `build_user_message(case, retrieved_policies)` that constructs the per-case user message from structured data.

The prompts are the interface between our system and the LLM. Their quality directly determines output reliability. Every design decision in the prompt — role framing, output schema placement, citation constraint, the "no preamble" instruction — is documented in System Design Section 7. Implement exactly what is specified there.

**Acceptance Criteria:**

**`SYSTEM_PROMPT` constant:**
- Defined at module level as a plain multi-line string
- Establishes the agent's role as a compliance decision agent operating in a regulated fintech environment
- States explicitly that decisions must be grounded only in the policies provided in the user message — outside knowledge is not permitted
- Defines all three decision options with their conditions: APPROVE for cases that clearly satisfy all policy requirements with no risk signals; DENY for cases that clearly violate one or more policies; ESCALATE for cases with uncertainty, conflicting signals, or insufficient information
- Lists all escalation trigger conditions explicitly: confidence below 0.65, missing or contradictory fields, conflicting policy signals, inability to ground the decision in provided policies
- Specifies the exact output schema the model must return, written out in full with field names, types, and the constraint that `policy_citations` may only reference `policy_id` values from the policies provided in the user message
- Contains a hard instruction at the end: return only the JSON object with no preamble, no explanation text, no markdown fencing, no trailing content of any kind
- Total length must not exceed 450 tokens (approximately 1,800 characters). Concise system prompts produce more reliable instruction-following than long ones.

**`build_user_message(case: Case, retrieved_policies: list[Policy]) -> str` function:**
- Accepts a `Case` model instance and a list of `Policy` model instances
- Returns a single formatted string that will be sent as the user turn to the API
- The message is structured in the following order with clear section labels:
  - Section 1 — Case identifier: displays `CASE: {case.case_id}`
  - Section 2 — Summary: displays the `case.summary` text under a `SUMMARY:` label
  - Section 3 — Case attributes: displays each attribute from `case.attributes` as a human-readable key-value pair, one per line, under a `CASE ATTRIBUTES:` label. Null values are displayed as `"not provided"` rather than `null` or `None`. Boolean values are displayed as `"yes"` / `"no"`. The `missing_fields` list is displayed as a comma-separated string or `"none"` if empty.
  - Section 4 — Retrieved policies: displays each policy under a `RELEVANT POLICIES:` label. For each policy, displays the `policy_id`, `title`, `rule`, and `escalation_note` (if present). Policies are separated by a blank line within this section.
  - Section 5 — Decision request: ends with the phrase `"Issue your decision now."`
- The function handles an empty `retrieved_policies` list gracefully — it displays a note in Section 4 that no policies were retrieved, which will cause the LLM to return ESCALATE as instructed in the system prompt
- Attribute keys are formatted as human-readable labels: `payout_amount` becomes `Payout Amount`, `identity_verified` becomes `Identity Verified`, etc. This formatting makes the LLM's job easier — structured labels in the prompt map more cleanly to policy language.

**Dependencies:** M1-T3 (config), M1-T4 (Case and Policy models)

**System Design Reference:** Section 4.4.1 (Prompt Architecture), Section 7 (Prompt Engineering Strategy), Section 7.1 (System Prompt Design Decisions), Section 7.4 (Anti-Patterns Avoided)

**Implementation Notes:**
- The system prompt must state the confidence threshold (0.65) explicitly. The model calibrates its own output confidence better when it knows the threshold it is being evaluated against. Do not leave this implicit.
- Format attribute keys by replacing underscores with spaces and applying title case. This is a single-line transformation and should not require a lookup table.
- The `missing_fields` list in case attributes is especially important to surface clearly in the user message. If a field is in `missing_fields`, the model needs to see this prominently, not buried in a list of attributes. Consider placing a clearly labeled `MISSING DATA:` line in the attributes section that lists these fields explicitly when non-empty.
- Do not include `expected_decision` or `difficulty` in the user message — these are evaluation metadata and must not be seen by the agent. Their presence in the prompt would leak ground truth to the model.
- The attribute formatting loop must handle all `Optional` fields — if a field's value is `None`, display `"not provided"`, never `"None"` (the Python string) or `"null"`. The string `"None"` in a prompt can confuse the model.

**Definition of Done:**
- `SYSTEM_PROMPT` is defined and contains all required elements — role, decision options, escalation conditions, output schema, no-preamble instruction
- `build_user_message(sample_case, sample_policies)` returns a string containing all five sections
- The returned string does not contain `expected_decision`, `difficulty`, or any evaluation metadata
- Null attribute values appear as `"not provided"` in the output, not as `"None"` or `"null"`
- `build_user_message(sample_case, [])` returns a string with a note about no retrieved policies in Section 4 without raising

---

## M4-T2: Implement the Anthropic API Client Wrapper

**Title:** Write the API call wrapper with error handling and rate-limit retry

**Description:**
Implement `call_anthropic_api(system_prompt: str, user_message: str) -> str` as a standalone function in `agent.py`. This function is responsible for making the API call to Claude and returning the raw text response. It is the only place in the codebase where the Anthropic SDK is used directly.

Isolating the API call in its own function serves two purposes: it makes the agent testable by allowing this function to be mocked in tests without mocking the entire agent class, and it concentrates all error handling for external API failures in one place.

**Acceptance Criteria:**
- `call_anthropic_api(system_prompt: str, user_message: str) -> str` calls `anthropic.Anthropic().messages.create()` with the following parameters, all sourced from `config.py`:
  - `model`: `config.MODEL_NAME`
  - `max_tokens`: `config.MAX_TOKENS`
  - `temperature`: `config.TEMPERATURE`
  - `system`: the provided `system_prompt` argument
  - `messages`: a list containing one user message with the provided `user_message` argument
- On success, returns `response.content[0].text` as a string
- On `anthropic.RateLimitError`: waits exactly 1 second (using `time.sleep(1)`) then retries the call once. If the retry also raises `RateLimitError`, raises it to the caller — no further retry.
- On `anthropic.AuthenticationError`: raises immediately with a descriptive message telling the developer to check their `ANTHROPIC_API_KEY` in `.env`. Does not retry.
- On `anthropic.APIConnectionError`: raises immediately. Does not retry. Network errors are not automatically retriable here — the caller's escalation path handles this.
- On any other `anthropic.APIError` subclass: raises immediately. Does not retry.
- On any non-Anthropic exception: raises immediately. Does not catch generic `Exception`.
- The function creates a new `anthropic.Anthropic()` client instance on each call. Do not store the client as a module-level singleton — this simplifies testing (no module-level patching needed) and avoids stale connection issues.

**Dependencies:** M1-T3 (config constants), M1-T2 (anthropic package installed)

**System Design Reference:** Section 4.4.2 (Agent Function), Section 8 (Error Handling Hierarchy — DecisionAgent row)

**Implementation Notes:**
- The 1-second rate-limit retry is deliberately simple. Production systems would use exponential backoff. For this assignment, a fixed 1-second wait is sufficient and keeps the code readable.
- Creating a new `Anthropic()` client per call is slightly less efficient than a shared client but makes the function fully self-contained. At 14 cases, the overhead is negligible.
- The `response.content[0].text` access assumes the API returns at least one content block. This is always true for a successful `messages.create` call with a text-only prompt, but add a guard: if `response.content` is empty, raise a `ValueError` with a message indicating unexpected empty response.
- Do not log the full API response anywhere — only the text content is returned. Never log request contents either, since the system prompt contains operational instructions that should not appear in logs.
- Import `time` from the standard library for the `sleep` call. No third-party sleep/retry libraries.

**Definition of Done:**
- The function is importable and callable with two string arguments
- When called with a valid API key and a well-formed prompt, it returns a non-empty string
- When the Anthropic client is mocked to raise `RateLimitError` twice in a row, the function sleeps once and then raises on the second failure (verified in `test_agent.py` in M6)
- The function does not catch generic `Exception` — only specific Anthropic error types

---

## M4-T3: Implement the DecisionAgent Class

**Title:** Build the DecisionAgent class that orchestrates the full single-case pipeline

**Description:**
Implement the `DecisionAgent` class in `agent.py`. This class is the central coordinator for a single case: it receives a `Case`, calls the retriever to get relevant policies, builds the prompt, calls the API, and returns the raw response and retrieved policies to the validator. Every step is wrapped in error handling that guarantees ESCALATE is returned if anything goes wrong.

**Acceptance Criteria:**

**Class design:**
- `DecisionAgent.__init__(self, retriever: PolicyRetriever)` accepts a `PolicyRetriever` instance and stores it as `self.retriever`. Does not create the retriever itself.
- `DecisionAgent.decide(self, case: Case) -> tuple[str, list[Policy]]` is the single public method
- The return type is always a tuple of: (raw JSON string, list of Policy objects that were retrieved). The raw JSON string is either the API response or a pre-built ESCALATE JSON string. The list is the retrieved policies (may be empty if retrieval failed).
- `decide` never raises. Every exception at every step is caught and results in a return of the escalation JSON string.

**Pipeline inside `decide`:**
- Step 1: Call `build_retrieval_query(case)` to build the enriched query string
- Step 2: Call `self.retriever.search(query)` to get retrieved policies. If the result is an empty list, immediately return the escalation JSON (retrieval failure path — see below). Do not call the API.
- Step 3: Call `build_user_message(case, retrieved_policies)` to construct the user message
- Step 4: Call `call_anthropic_api(SYSTEM_PROMPT, user_message)`. If this raises any exception, catch it and return the escalation JSON.
- Step 5: Return the API response string and the retrieved policies list as a tuple

**Escalation JSON method:**
- `DecisionAgent._build_escalation_response(self, case_id: str, reason: str, retrieved: list[Policy]) -> str` is a private method that constructs a valid ESCALATE JSON string
- The JSON string it produces must be parseable and must pass Pydantic validation in the validator — it must include all required fields: `decision`, `confidence`, `policy_citations`, and enough data for `audit_log` to be constructed by the validator
- `confidence` in the escalation response is always `0.0`
- `policy_citations` contains exactly one entry. The `policy_id` is the first retrieved policy's ID if the list is non-empty, otherwise `"POL-007"` (the missing data policy, which is always relevant when the system cannot process a case). The `reason` is the escalation reason string passed into the method.
- This method must never raise — it constructs the JSON using Python's `json.dumps()` on a plain dict, not by instantiating Pydantic models (which could fail)

**Dependencies:** M4-T1 (prompts and message builder), M4-T2 (API caller), M3-T1 (PolicyRetriever), M3-T2 (query builder), M1-T4 (models)

**System Design Reference:** Section 4.4.2 (Agent Function), Section 3.2 (Data Flow), Section 8 (Error Handling Hierarchy)

**Implementation Notes:**
- The `decide` method uses a broad `try/except Exception` at the outermost level as a last-resort safety net. However, inner steps (retrieval, API call) should have their own specific error handling first — the outer catch is for truly unexpected errors only. This layered approach means error messages in the escalation response are specific rather than generic.
- The `retrieved` variable must be initialized to an empty list `[]` before the try block so that if the retrieval step itself raises (before assigning to `retrieved`), the escalation response can still be built without a `NameError`.
- `build_retrieval_query` is a pure function that should not raise under normal circumstances — but it is still inside the try block as a defensive measure.
- The audit log is NOT constructed by `DecisionAgent`. The raw response string contains the decision, confidence, and citations. The validator constructs the full `DecisionOutput` including the `audit_log`. The agent's only job is to return the raw string.
- Do not serialize the `Case` object or any of its attributes into the raw escalation JSON. The escalation JSON must only contain what the `DecisionOutput` Pydantic model expects.

**Definition of Done:**
- `agent = DecisionAgent(retriever); result, policies = agent.decide(sample_case)` executes without error
- `result` is a non-empty string that is valid JSON
- When the retriever mock returns an empty list, `agent.decide()` returns ESCALATE JSON without calling the API
- When `call_anthropic_api` is mocked to raise `Exception("network error")`, `agent.decide()` returns ESCALATE JSON with the exception message in the reason
- The tuple `(str, list)` is always returned — never `None`, never a single value

---

## M4-T4: Add Direct-Run Test Mode to agent.py

**Title:** Add a manual smoke test mode that runs one real case end-to-end

**Description:**
Add a `if __name__ == "__main__":` block to `agent.py` that runs a single case through the full pipeline when the file is executed directly. This is not a unit test — it is a developer smoke test that confirms the API connection, retrieval, and prompt construction all work together before the full evaluation in M6.

**Acceptance Criteria:**
- When `python agent.py` is run from the project root:
  - Loads `cases.json` and selects the first case (CASE-001)
  - Instantiates `PolicyRetriever('policies.md')`
  - Instantiates `DecisionAgent(retriever)`
  - Calls `agent.decide(case)` on CASE-001
  - Prints the following to stdout, clearly labeled:
    - `Case ID:` followed by the case ID
    - `Retrieved Policies:` followed by a comma-separated list of retrieved policy IDs
    - `Raw Response:` followed by the raw JSON string from the API
  - Exits cleanly with no exception
- If the `.env` file is missing or `ANTHROPIC_API_KEY` is not set, the run fails with a clear error message rather than an obscure `NoneType` error
- The smoke test makes exactly one real API call using real credentials

**Dependencies:** M4-T3 (DecisionAgent), M3-T1 (PolicyRetriever), M2-T1 (policies.md), M2-T2 (cases.json)

**System Design Reference:** Section 4.4.2, Section 9.1 (Secret Management)

**Implementation Notes:**
- The API key check should happen at the top of the `__main__` block before any expensive initialization. Check `config.ANTHROPIC_API_KEY` is not `None` or empty, and print a clear message and `sys.exit(1)` if it is absent.
- This is a real API call — it will consume a small amount of API credits. Document this in a comment so developers don't run it repeatedly by accident.
- Do not hardcode a case — always load from `cases.json` so the smoke test reflects the actual data.
- The `Raw Response:` output will be a JSON string. Do not pretty-print it at this stage — raw output is more useful for debugging.

**Definition of Done:**
- `python agent.py` runs and prints all three labeled outputs without crashing
- The raw response is a valid JSON string (not an error message)
- Running the file twice produces consistent results for CASE-001 (same decision, same cited policies)

---

# MILESTONE 5: Validator & Escalation

**Goal:** Build the complete validation and escalation layer in `validator.py`. This is the layer that sits between the agent's raw output and the final `DecisionOutput`. After M5, the full pipeline from case input to validated structured output is complete. A call to `run_pipeline(case, agent)` returns a fully validated, escalation-checked `DecisionOutput` or raises nothing — ever.

**Completion signal:** Running `python validator.py` processes CASE-001 through the full pipeline (agent + validator + escalation checker) and prints a formatted `DecisionOutput` JSON. Running it on CASE-013 (missing fields) produces a `DecisionOutput` with `decision: "ESCALATE"`.

---

## M5-T1: Implement Output Parsing and Pydantic Validation

**Title:** Write the JSON parser and Pydantic validator for raw agent output

**Description:**
Implement `parse_and_validate(raw_response: str, case_id: str, retrieved: list[Policy]) -> tuple[DecisionOutput | None, str | None]` in `validator.py`. This function attempts to parse the agent's raw JSON string and validate it against the `DecisionOutput` Pydantic model. It returns either a valid model instance or `None` paired with an error description string.

This function is called by the retry orchestrator in M5-T2. It must never raise — it always returns a tuple indicating success or failure.

**Acceptance Criteria:**
- The function signature is `parse_and_validate(raw_response: str, case_id: str, retrieved: list[Policy]) -> tuple[DecisionOutput | None, str | None]`
- The return value is always one of:
  - `(DecisionOutput_instance, None)` on full success
  - `(None, error_description_string)` on any failure
- The function never raises under any circumstances — all exceptions are caught internally

**JSON parsing step:**
- Attempts `json.loads(raw_response)` to parse the raw string
- If parsing fails with `json.JSONDecodeError`, returns `(None, f"JSON parse error: {error message}")` immediately
- Before parsing, applies a cleaning step that strips any markdown code fences (triple backticks with or without a language tag) from the raw response. The LLM sometimes wraps its output in `json...` despite being instructed not to. Strip these if present before attempting to parse.

**Pydantic validation step:**
- Constructs a partial dict from the parsed JSON — adds `case_id` from the function argument (not from the JSON, since the LLM output does not include `case_id` per the schema)
- Constructs the `audit_log` dict with: `retrieved_policies` as the list of retrieved policy IDs, `retrieval_score` as the highest `similarity_score` among retrieved policies (or `0.0` if list is empty), `timestamp` as the current UTC time in ISO 8601 format, `retry_attempted` as `False` (the retry flag is set by the orchestrator, not here), `error_detail` as `None`
- Attempts `DecisionOutput(**constructed_dict)` to instantiate the Pydantic model
- If instantiation raises `ValidationError`, returns `(None, f"Validation error: {error.errors()}")` with the full Pydantic error detail
- If instantiation succeeds, returns `(output, None)`

**Citation integrity check:**
- After successful Pydantic validation, performs a citation integrity check: verifies that every `policy_id` in `output.policy_citations` is present in the list of retrieved policy IDs
- If any citation references a policy that was NOT retrieved, that citation is removed from the list and an `error_detail` note is added to `audit_log` naming the removed policy IDs
- If removing invalid citations results in an empty `policy_citations` list, returns `(None, "All citations were invalid — no retrieved policy IDs were cited")` so the retry path fires
- This check is performed by calling `output.model_copy(update=...)` — the model itself is not mutated

**Dependencies:** M1-T4 (all Pydantic models), M4-T1 (for understanding of agent output format)

**System Design Reference:** Section 4.5.1 (Validation Pipeline), Section 4.5 (validator.py)

**Implementation Notes:**
- The `case_id` is injected into the output by the validator, not produced by the LLM. The agent's system prompt does not ask the LLM to include `case_id` in its response because it is structural metadata, not a reasoning output. The validator has it from the original `Case` object and attaches it here.
- The UTC timestamp must use `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` (import `timezone` from `datetime`) — not `datetime.now()` without timezone, which returns local time. The assignment's example output uses ISO 8601 UTC format.
- The `retrieval_score` in `audit_log` uses the highest similarity score across retrieved policies. If three policies were retrieved with scores `[0.71, 0.55, 0.43]`, the `retrieval_score` is `0.71`. This represents "how well the best matching policy matched" — useful for evaluating retrieval quality.
- Removing citations in the integrity check must use `model_copy(update={"policy_citations": filtered_list})` — direct attribute assignment on a Pydantic model is unreliable even when not frozen.
- The `error_detail` appended during citation removal must be a string, not a list. Join removed IDs with a comma if multiple are removed.

**Definition of Done:**
- `parse_and_validate(valid_json_string, "CASE-001", retrieved_policies)` returns a tuple with a non-None `DecisionOutput` as the first element
- `parse_and_validate('{"bad json', "CASE-001", [])` returns `(None, "JSON parse error: ...")`
- `parse_and_validate('{"decision": "APPROVE", "confidence": 1.5, "policy_citations": [...]}', ...)` returns `(None, "Validation error: ...")` because confidence is out of range
- `parse_and_validate(json_with_invalid_citation, "CASE-001", retrieved)` removes the invalid citation and returns a valid output with an `error_detail` note in the audit log
- The function never raises — wrapping it in `try/except Exception` in a test always reaches the return statement

---

## M5-T2: Implement the Retry Orchestrator

**Title:** Write the retry logic that attempts validation once and escalates on second failure

**Description:**
Implement `validate_with_retry(raw_response: str, case_id: str, retrieved: list[Policy], agent: DecisionAgent, case: Case) -> DecisionOutput` in `validator.py`. This function calls `parse_and_validate` on the initial response. If it fails, it constructs a correction prompt, calls the API once more via the agent, and attempts `parse_and_validate` again. If the second attempt also fails, it returns a hardcoded ESCALATE `DecisionOutput`.

**Acceptance Criteria:**

**First attempt:**
- Calls `parse_and_validate(raw_response, case_id, retrieved)` immediately
- If the result is a valid `DecisionOutput`, sets `retry_attempted = False` on the audit log and returns the output
- If the result is `None`, proceeds to the retry step

**Retry step:**
- Builds a correction prompt string using the template defined in System Design Section 4.5.2. The correction prompt must include:
  - The specific error message returned by the first `parse_and_validate` call
  - The invalid response text that caused the failure
  - A reminder of the exact required output schema
  - The original user message (re-constructed from the case and retrieved policies using `build_user_message`)
- Calls `call_anthropic_api(SYSTEM_PROMPT, correction_prompt)` to get a second response
- If `call_anthropic_api` raises, catches the exception and proceeds to the escalation fallback
- Calls `parse_and_validate(retry_response, case_id, retrieved)` on the second response
- If the second attempt succeeds, sets `retry_attempted = True` on the audit log and returns the output
- If the second attempt also fails, proceeds to the escalation fallback

**Escalation fallback (both attempts failed):**
- Constructs and returns a `DecisionOutput` object directly (not via the agent's `_build_escalation_response`, since that returns a string — here we return a model instance)
- The escalation `DecisionOutput` has:
  - `case_id`: the provided `case_id`
  - `decision`: `"ESCALATE"`
  - `confidence`: `0.0`
  - `policy_citations`: one entry using the first retrieved policy ID (or `"POL-007"` if none) with reason `"Automatic escalation: output validation failed after retry"`
  - `audit_log`: fully populated with `retry_attempted: True`, `error_detail` containing both the first and second validation error messages concatenated
- This fallback must be constructed from plain dicts using `DecisionOutput(**dict)` — if Pydantic validation fails here, something is fundamentally broken with the model, and the exception should be allowed to propagate (this is a programmer error, not a runtime error)

**Dependencies:** M5-T1 (parse_and_validate), M4-T1 (build_user_message, SYSTEM_PROMPT), M4-T2 (call_anthropic_api), M4-T3 (DecisionAgent type reference)

**System Design Reference:** Section 4.5.2 (Retry Strategy), Section 8 (Error Handling — OutputValidator row)

**Implementation Notes:**
- Import `call_anthropic_api` and `build_user_message` from `agent.py` at the top of `validator.py`. This is not a circular import because `agent.py` does not import from `validator.py`.
- The correction prompt must include the original user message — not just the error. Experience shows that re-sending the context alongside the error description produces far better correction than sending only the error. The LLM needs to see what it was supposed to decide on.
- The `retry_attempted` flag in `audit_log` uses `model_copy(update={"audit_log": audit_log.model_copy(update={"retry_attempted": True})})`. This nested model_copy is necessary because `AuditLog` is a nested Pydantic model inside `DecisionOutput`.
- Do not modify the original `raw_response` argument — the retry uses a fresh `correction_prompt`, not a modified version of the original prompt.
- The escalation fallback constructs its audit_log with `error_detail` that contains both errors so the operator knows both attempts failed. Format as: `"Attempt 1: {error1} | Attempt 2: {error2}"`.

**Definition of Done:**
- `validate_with_retry(valid_json, "CASE-001", retrieved, agent, case)` returns a `DecisionOutput` with `retry_attempted: False`
- When first attempt fails and second succeeds (mocked), returns output with `retry_attempted: True`
- When both attempts fail (mocked), returns ESCALATE `DecisionOutput` with `retry_attempted: True` and `error_detail` containing both error messages
- The function never raises under any of these three conditions

---

## M5-T3: Implement the EscalationChecker

**Title:** Build the deterministic post-validation escalation override layer

**Description:**
Implement the `EscalationChecker` class in `validator.py`. This class receives a validated `DecisionOutput` and applies deterministic system-level escalation rules regardless of what the LLM decided. It is the final layer before output is returned to the caller.

This is not second-guessing the LLM — it is enforcing system-level safety constraints that belong in code, not in a prompt. A missing field is a structural fact, not an LLM judgment call. A confidence score below threshold is a measurable property. These rules are transparent, testable, and operator-reviewable.

**Acceptance Criteria:**

**`EscalationChecker.check(self, output: DecisionOutput, case: Case, retrieved: list[Policy]) -> DecisionOutput`:**
- Applies the following rules in order, collecting all triggered reasons before overriding:

  Rule 1 — Confidence below threshold:
  - Reads `output.confidence` and compares to `config.CONFIDENCE_THRESHOLD` (0.65)
  - If `output.confidence < CONFIDENCE_THRESHOLD`, adds a reason: `f"Confidence {output.confidence:.2f} is below required threshold {CONFIDENCE_THRESHOLD}"`

  Rule 2 — Missing critical fields:
  - Checks `config.ESCALATE_ON_MISSING_FIELDS` is `True`
  - Checks `case.attributes.missing_fields` is non-empty
  - If both conditions are true, adds a reason: `f"Case has missing critical fields: {', '.join(case.attributes.missing_fields)}"`

  Rule 3 — Empty retrieval:
  - Checks `config.ESCALATE_ON_RETRIEVAL_FAILURE` is `True`
  - Checks `retrieved` is an empty list
  - If both conditions are true, adds a reason: `"No policies were retrieved for this case"`

  Rule 4 — Conflicting core identity signals:
  - Checks for deterministic contradictions in case data (for example: `identity_verified == true` while names conflict, or either name is `"UNKNOWN"`)
  - If conflict is detected, adds a reason: `"Conflicting identity signals detected in case attributes"`

- If no reasons were collected, returns the output unchanged — no modification at all
- If one or more reasons were collected AND the current decision is already `"ESCALATE"`, returns the output unchanged (already escalated — no override needed, but adds the reasons to `error_detail` if `error_detail` is currently `None`)
- If one or more reasons were collected AND the current decision is `"APPROVE"` or `"DENY"`, overrides the decision to `"ESCALATE"` using `model_copy`:
  - Sets `decision` to `"ESCALATE"`
  - Appends an `error_detail` to the audit log: `"Escalation override applied. Reasons: " + "; ".join(reasons)`
  - Does NOT change `confidence`, `policy_citations`, or any other field — the full reasoning trail is preserved
- The `check` method never raises. Wraps the entire body in `try/except Exception` as a last-resort safety net — if the escalation checker itself crashes, returns the original output unchanged (better to pass through an unescalated output than to crash the pipeline)

**Dependencies:** M1-T3 (config thresholds), M1-T4 (DecisionOutput, Case models)

**System Design Reference:** Section 4.5.3 (EscalationChecker), Section 2 (Architecture Philosophy — Fail Toward Safety), Section 2.3 (No Hidden Logic)

**Implementation Notes:**
- The rules are evaluated independently and can all trigger simultaneously. Collect all reasons before deciding whether to override — do not short-circuit after the first triggered rule.
- The order matters for the `error_detail` string: confidence reason comes first, then missing fields, then retrieval failure, then conflicting signals. This order makes audit logs consistent and readable.
- Rule 3 (empty retrieval) should rarely fire here because the agent already returns ESCALATE JSON when retrieval is empty. However, the EscalationChecker does not trust upstream behavior — it independently verifies.
- When overriding decision from DENY to ESCALATE: the policy citations that supported the DENY reasoning remain in the output. An operator reviewing the escalation can read the citations and understand what the agent was going to deny for, and why the system overrode it. This is the audit trail working as intended.
- "No modification at all" when no reasons are collected means `return output` — the same object, not a copy. Pydantic models are not frozen, so this is safe and avoids unnecessary object creation.

**Definition of Done:**
- `checker.check(output_with_confidence_0.4, case_without_missing_fields, retrieved)` returns output with `decision: "ESCALATE"`
- `checker.check(output_with_confidence_0.9, case_without_missing_fields, retrieved)` returns output unchanged
- `checker.check(output_with_confidence_0.9, case_with_missing_fields, retrieved)` returns output with `decision: "ESCALATE"` regardless of original decision
- `checker.check(already_escalated_output, case_with_missing_fields, retrieved)` returns the already-escalated output without double-modifying it
- `checker.check(output_with_confidence_0.9, case_with_conflicting_identity_signals, retrieved)` returns output with `decision: "ESCALATE"` regardless of original decision
- When `checker.check` is called and an exception is raised inside (mocked), it returns the original output unchanged

---

## M5-T4: Implement run_pipeline and Smoke Test

**Title:** Wire all pipeline stages into a single run_pipeline function and add direct-run validation

**Description:**
Implement `run_pipeline(case: Case, agent: DecisionAgent) -> DecisionOutput` in `validator.py`. This is the single public function that external callers (`evaluate.py`) use. It orchestrates the agent call, validation with retry, and escalation checking into one clean, never-raises function call.

**Acceptance Criteria:**

**`run_pipeline(case: Case, agent: DecisionAgent) -> DecisionOutput`:**
- Step 1: Calls `agent.decide(case)` — receives `(raw_response, retrieved_policies)`
- Step 2: Calls `validate_with_retry(raw_response, case.case_id, retrieved_policies, agent, case)` — receives a `DecisionOutput`
- Step 3: Calls `EscalationChecker().check(output, case, retrieved_policies)` — receives the final `DecisionOutput`
- Step 4: Returns the final `DecisionOutput`
- The function never raises. Wraps the entire body in a `try/except Exception` last-resort safety net. If the catch fires, constructs and returns a minimal ESCALATE `DecisionOutput` with `error_detail` describing the exception.
- Returns a `DecisionOutput` on every call — never `None`, never raises

**`if __name__ == "__main__"` block:**
- Loads cases from `cases.json`
- Selects and runs two specific cases: CASE-001 (straightforward APPROVE) and CASE-013 (edge case ESCALATE)
- For each case, prints:
  - The case ID and difficulty
  - The final `decision` and `confidence`
  - The `policy_citations` (IDs and reasons)
  - Whether `retry_attempted` was True
  - The `error_detail` if present
- Exits cleanly
- This makes exactly 2 real API calls — document this in a comment

**Dependencies:** M5-T1, M5-T2, M5-T3, M4-T3

**System Design Reference:** Section 3.2 (Data Flow — End to End), Section 2.4 (Fail Toward Safety)

**Implementation Notes:**
- `run_pipeline` instantiates `EscalationChecker()` on each call. It is stateless, so this is perfectly fine. No need to pass it in as a dependency.
- The last-resort `try/except` in `run_pipeline` should log the exception message to stderr before returning the escalation output — this is important for debugging cases where the pipeline itself breaks.
- The `DecisionOutput` constructed in the last-resort catch is built from a plain dict, same pattern as the escalation fallback in M5-T2. It must be valid against the Pydantic model — if constructing this also fails, re-raise. We cannot silently hide a broken Pydantic model.
- The smoke test output should be human-readable and formatted, not a raw JSON dump. Use clean `print(f"...")` statements. This is what a developer runs during debugging — make it easy to read.

**Definition of Done:**
- `run_pipeline(case_001, agent)` returns a `DecisionOutput` with `decision` in `["APPROVE", "DENY", "ESCALATE"]`
- `run_pipeline(case_013, agent)` returns a `DecisionOutput` with `decision == "ESCALATE"`
- `python validator.py` runs, makes 2 API calls, prints readable output for both cases, exits cleanly
- The function never raises under any mocked failure scenario (agent fails, validator fails, checker fails) — always returns a `DecisionOutput`

---

# MILESTONE 6: Evaluation, Tests, and Deliverable Documents

**Goal:** Complete all remaining deliverables: the batch evaluation script, the test suite, `design.md`, and `README.md`. After M6, the project is fully complete and ready to submit. The evaluation script must run all 14 cases and produce the formatted metrics report. Tests must pass. Documentation must be clear and honest.

**Completion signal:** `pytest tests/ -v` passes all tests with no failures. `python evaluate.py` runs all 14 cases and prints the metrics report. The repo is clean with no committed `.env`, no `__pycache__`, no stray files.

---

## M6-T1: Implement evaluate.py

**Title:** Build the batch evaluation script with metrics computation and formatted output

**Description:**
Implement `evaluate.py` as a self-contained script that loads all cases, runs each through `run_pipeline`, collects results, computes metrics, and prints the formatted evaluation report defined in System Design Section 4.6.2. This is the primary deliverable the evaluator will run when reviewing the submission.

**Acceptance Criteria:**

**Case processing:**
- Loads all cases from `cases.json` using `json.load` and validates each against the `Case` Pydantic model
- Instantiates `PolicyRetriever` and `DecisionAgent` once before the processing loop — not once per case
- Processes each case sequentially using `run_pipeline(case, agent)`
- If a single case raises an unexpected exception (should never happen given `run_pipeline`'s safety net, but defended against here), logs the error to stderr, marks the case as FAIL with decision "ESCALATE" in the results, and continues to the next case — never aborts the full run
- Collects `EvalResult` objects for each case containing: `case_id`, `difficulty`, `expected`, `got`, `confidence`, `retry_attempted`

**Metrics computation:**
- Computes all metrics defined in System Design Section 4.6.1:
  - Total cases
  - Count of APPROVE, DENY, ESCALATE decisions
  - Overall accuracy (correct decisions / total cases)
  - Percentage of ambiguous cases that were escalated
  - Percentage of straightforward cases that were NOT escalated
  - Percentage of edge cases that were escalated
- Each percentage metric is accompanied by a raw fraction (e.g., `75.0% (3/4)`) for transparency
- Accuracy denominator is always 14 — never skip failed cases from accuracy calculation

**Output format:**
- Prints the exact formatted report defined in System Design Section 4.6.2
- Includes the target thresholds next to each metric so the evaluator can immediately see pass/fail status
- Per-case breakdown lists every case on its own line with: case ID, difficulty, expected decision, actual decision, PASS/FAIL indicator
- Total runtime is printed at the end in seconds (use `time.time()` before and after the loop)
- Output goes to stdout. Errors (individual case failures) go to stderr. This allows the evaluator to redirect stdout to a file cleanly.

**`if __name__ == "__main__"` gate:**
- The entire script logic is inside `if __name__ == "__main__":` so the file can be imported in tests without triggering execution
- Exits with code `0` if overall accuracy ≥ 70% (reasonable baseline), exits with code `1` otherwise

**Dependencies:** M5-T4 (run_pipeline), M3-T1 (PolicyRetriever), M4-T3 (DecisionAgent), M2-T2 (cases.json)

**System Design Reference:** Section 4.6 (evaluate.py), Section 4.6.1 (Metrics Design), Section 4.6.2 (Output Format)

**Implementation Notes:**
- Print a progress indicator during the run: `"Processing CASE-001 (1/14)..."` before each case. At 14 cases with real API calls, the run takes 20–40 seconds. A progress indicator prevents the evaluator from thinking the script has frozen.
- Do not batch API calls or run cases in parallel. Sequential processing keeps the run predictable and avoids rate limit issues. At 14 cases, parallelism provides negligible time savings.
- The `EvalResult` type can be a `dataclass` or a `TypedDict` — it does not need to be a Pydantic model since it is only used internally within `evaluate.py`.
- Compute metrics after the processing loop completes — not incrementally. Store all raw results, then derive all metrics at once. This makes it easy to add new metrics later.
- The exit code logic is the last statement in the file. `sys.exit(0)` or `sys.exit(1)` based on accuracy.

**Definition of Done:**
- `python evaluate.py` runs all 14 cases and prints the full formatted report
- The per-case breakdown shows all 14 cases with PASS/FAIL indicators
- Overall accuracy and all three tier metrics are printed with raw fractions
- Total runtime in seconds is displayed
- Exit code is `0` when accuracy ≥ 70%, `1` otherwise (verifiable with `echo $?` after running)

---

## M6-T2: Write the Test Suite

**Title:** Implement all four test files with complete unit test coverage of critical paths

**Description:**
Implement the test suite across all four test files. Tests must be genuine unit tests with proper mocking of the Anthropic API — no real API calls in any test. The test suite covers the most critical behavioral requirements: retrieval accuracy, validation failure paths, retry behavior, and metrics computation correctness.

**Acceptance Criteria:**

**`tests/test_retriever.py` — minimum 4 tests:**

Test 1 — Load policies:
- Creates a temporary `policies.md` with two minimal policy blocks
- Calls `load_policies` on it
- Asserts 2 `Policy` objects are returned
- Asserts each has non-empty `policy_id`, `title`, and `rule`

Test 2 — Search returns relevant policies:
- Instantiates `PolicyRetriever` with the real `policies.md`
- Calls `search("identity not verified payout denied")`
- Asserts the first result has `policy_id == "POL-001"`
- Asserts the first result has `similarity_score > 0.0`

Test 3 — Search returns empty list for no-match query:
- Instantiates `PolicyRetriever` with the real `policies.md`
- Calls `search("xyzabc completely unrelated gibberish terms")`
- Asserts the result is an empty list `[]`

Test 4 — build_retrieval_query enriches correctly:
- Constructs a `Case` object with `high_risk_flag: True` and a name mismatch
- Calls `build_retrieval_query(case)`
- Asserts the result contains `"high risk"` and `"name mismatch"`

**`tests/test_validator.py` — minimum 4 tests:**

Test 1 — parse_and_validate succeeds on valid JSON:
- Constructs a valid JSON string matching the output schema
- Calls `parse_and_validate` with it and a list of matching retrieved policies
- Asserts the first return value is a `DecisionOutput` instance
- Asserts the second return value is `None`

Test 2 — parse_and_validate fails on invalid JSON:
- Calls `parse_and_validate('{"broken json', "CASE-001", [])`
- Asserts the first return value is `None`
- Asserts the second return value is a non-empty string containing "JSON"

Test 3 — EscalationChecker overrides low-confidence output:
- Constructs a `DecisionOutput` with `decision: "APPROVE"` and `confidence: 0.40`
- Calls `EscalationChecker().check(output, case_without_missing_fields, retrieved)`
- Asserts the returned output has `decision: "ESCALATE"`
- Asserts `error_detail` in audit log is non-None

Test 4 — validate_with_retry escalates after two failures:
- Mocks `call_anthropic_api` to return `'{"bad": "json"}'` on both calls
- Calls `validate_with_retry` with an invalid initial response
- Asserts the returned output has `decision: "ESCALATE"` and `retry_attempted: True`

**`tests/test_agent.py` — minimum 3 tests:**

Test 1 — agent.decide returns ESCALATE when retriever returns empty list:
- Mocks `PolicyRetriever.search` to return `[]`
- Calls `agent.decide(sample_case)`
- Asserts the returned raw JSON string parses to a dict with `decision: "ESCALATE"`
- Asserts the API was NOT called (mock call count is 0)

Test 2 — agent.decide returns ESCALATE when API raises:
- Mocks `call_anthropic_api` to raise `Exception("connection failed")`
- Calls `agent.decide(sample_case)`
- Asserts the returned raw JSON string parses to a dict with `decision: "ESCALATE"`

Test 3 — agent.decide returns raw response on API success:
- Mocks `call_anthropic_api` to return a valid JSON string
- Calls `agent.decide(sample_case)`
- Asserts the first return value equals the mocked response string
- Asserts the second return value is a non-empty list of `Policy` objects

**`tests/test_evaluate.py` — minimum 2 tests:**

Test 1 — Metrics computation: straightforward accuracy:
- Constructs 4 `EvalResult` objects where 3 match expected (accuracy = 75%)
- Calls `compute_metrics(results)` (exported from `evaluate.py`)
- Asserts `accuracy == 0.75`
- Asserts counts are correct

Test 2 — Metrics computation: ambiguous escalation rate:
- Constructs 4 `EvalResult` objects all with `difficulty: "ambiguous"`, 3 of which have `got: "ESCALATE"`
- Calls `compute_metrics(results)`
- Asserts `ambiguous_escalated_pct == 0.75`

**General test requirements:**
- Every test has a clear docstring (one sentence) describing what it is testing
- No test makes a real API call — all Anthropic client interactions are mocked using `pytest-mock`
- All tests are independent — no shared state, no test ordering dependencies
- `pytest tests/ -v` runs all tests and each test name clearly describes what it is testing

**Dependencies:** All prior milestones (M1–M5), M6-T1 (for evaluate.py exports)

**System Design Reference:** Section 10 (Testing Strategy), Section 10.2 (Mocking Strategy), Section 10.3 (Critical Test Cases)

**Implementation Notes:**
- `compute_metrics` must be exported from `evaluate.py` as a standalone function, not just used inside `__main__`. The test file imports it directly.
- Use `pytest.fixture` for shared test objects: a `sample_case` fixture that returns a valid `Case` instance, and a `sample_retrieved` fixture that returns a list with one `Policy`. Define these in a `conftest.py` file in the `tests/` directory.
- For mocking `call_anthropic_api`, use `mocker.patch("agent.call_anthropic_api", return_value=valid_json_string)`. The patch target is the function as imported in `agent.py`, not in the test module.
- Constructing valid test JSON strings manually is error-prone. Define a `VALID_DECISION_JSON` constant in `conftest.py` that is a valid JSON string for an APPROVE decision with one citation. Reuse it across test files.

**Definition of Done:**
- `pytest tests/ -v` exits with code `0`
- All tests have docstrings
- No test makes a real API call (verified by checking no `anthropic.Anthropic()` instantiation occurs without mocking)
- Test names clearly describe what is being tested when printed by pytest

---

## M6-T3: Write design.md

**Title:** Author the one-page system design writeup as specified in the assignment

**Description:**
Write `design.md` as a concise, technically honest one-page document that answers the four questions in the assignment directly. This is the document the evaluator reads when forming an impression of your thinking. It must be sharp, direct, and show genuine reasoning — not marketing language.

**Acceptance Criteria:**
- `design.md` answers all four assignment questions with these exact section headers:
  - `## How the system works`
  - `## When and why we escalate`
  - `## Biggest failure case`
  - `## One thing I'd improve with more time`
- Total length: 300–500 words. No longer. Brevity demonstrates clarity of thought.
- Tone: direct, technical, first-person where appropriate. No filler phrases ("I am excited to share", "This demonstrates my ability to"). No passive voice where active voice is clearer.

**Content requirements per section:**

How the system works:
- Describes the pipeline in one paragraph: case input → enriched query → TF-IDF retrieval of top-3 policies → prompt construction (case + policies) → Claude API call → Pydantic validation → escalation override check → structured output
- Explains the key design choice: decisions are grounded in retrieved policy text, not freeform LLM reasoning. Mentions why TF-IDF was chosen over embeddings at this scale.
- States the reliability mechanism: output validated against a strict schema, retry once on failure, ESCALATE on second failure

When and why we escalate:
- Lists the five concrete escalation triggers (in plain English, not code): confidence below 0.65, missing critical fields, conflicting signals in case data, policy retrieval failure, output validation failure after retry
- Makes the philosophical point: ESCALATE is a first-class outcome, not a fallback. In regulated environments, uncertain decisions belong with humans, not automated systems.

Biggest failure case:
- Names the real weakness honestly: TF-IDF retrieval on short policy documents can return poor matches when the case uses vocabulary that doesn't directly appear in the policy text. A case described as "unusual transaction pattern" may not retrieve POL-005 (profile change velocity) even though it is relevant, because the vocabulary doesn't overlap.
- This is a genuine limitation, not a minor caveat. Acknowledging it demonstrates understanding of the system's actual failure mode.

One thing I'd improve with more time:
- Answers with: replace TF-IDF with a proper embedding-based retrieval step using a small local model (e.g., `sentence-transformers`). This would capture semantic similarity rather than just term overlap, solving the vocabulary mismatch problem described above. The rest of the pipeline stays the same — retrieval is the only module that changes.
- Optionally mentions: adding a confidence calibration step where the LLM's stated confidence is compared against historical accuracy on similar cases and adjusted accordingly.

**Dependencies:** All prior milestones — design.md can only be written accurately after the system is built and tested.

**System Design Reference:** Section 7.2 (Temperature Rationale), Section 4.3.1 (Why TF-IDF), Section 12 (What We Are NOT Building)

**Implementation Notes:**
- Write this after running `python evaluate.py` once so the accuracy numbers are real. If accuracy is below target, this is relevant context for the "biggest failure case" section — be honest about it.
- The "biggest failure case" answer must be specific and technical, not generic ("the LLM might make mistakes"). Any evaluator can write the generic answer. The specific TF-IDF vocabulary mismatch problem shows you actually understand how the retrieval layer works and where it breaks down.
- Do not pad this document with architecture diagrams, tables, or bullet lists. It should read as three tight paragraphs and one short paragraph. Evaluators at this level prefer prose that respects their time.

**Definition of Done:**
- `design.md` contains all four section headers
- Total word count is between 300 and 500 words
- The "biggest failure case" section names a specific, technically accurate failure mode — not a generic disclaimer
- No marketing language or filler phrases appear anywhere in the document

---

## M6-T4: Write README.md

**Title:** Write a complete, accurate README with setup and run instructions

**Description:**
Write `README.md` as the entry point for anyone who clones the repository. It must be complete enough that the evaluator can go from fresh clone to running `python evaluate.py` without asking a single question or encountering an undocumented step.

**Acceptance Criteria:**
- `README.md` contains the following sections in this order:
  - Project title and one-sentence description
  - `## Requirements` — Python version, note that pip packages are in `requirements.txt`
  - `## Setup` — exact steps: clone, create virtualenv, `pip install -r requirements.txt`, copy `.env.example` to `.env`, add API key
  - `## Running the evaluation` — exact command: `python evaluate.py`, description of expected output
  - `## Running a single case` — exact command: `python validator.py`, description of output
  - `## Running tests` — exact command: `pytest tests/ -v`, expected output description
  - `## Project structure` — brief description of each file's responsibility (one line each)
  - `## Design decisions` — two-sentence note pointing to `design.md` for full details, with one inline sentence summarizing the key architectural decision (TF-IDF retrieval, Pydantic validation, ESCALATE-first reliability model)

- Every command in the README has been manually run and confirmed to work before the README is written
- The virtualenv setup uses `python -m venv venv` and `source venv/bin/activate` (Unix) — note that Windows uses `venv\Scripts\activate`
- The `.env` setup section shows the exact contents of `.env.example` so the evaluator knows exactly what to add without opening another file
- No broken links, no placeholder text (`TODO`, `[your name here]`), no commands that don't work

**Dependencies:** All prior milestones.

**System Design Reference:** Section 9.1 (Secret Management), Section 8 (File Structure)

**Implementation Notes:**
- Write the README last — after everything else works. A README written before the code is built inevitably contains inaccuracies.
- The project structure section maps to the System Design Section 8 file listing. Each file gets one line: filename + its single responsibility.
- Keep the README practical and short. The evaluator has seen hundreds of READMEs. A clean, correct, complete README in 150–200 lines is better than an elaborate one with broken commands.

**Definition of Done:**
- Every command in the README runs exactly as written without modification
- No section contains placeholder text
- A developer with Python 3.11 and no prior context can follow the README from clone to `python evaluate.py` without needing to ask anything

---

## M6-T5: Final Cleanup and Submission Readiness Check

**Title:** Run the complete submission checklist before finalizing

**Description:**
This is not a coding ticket. It is a systematic verification pass that confirms the complete submission is correct, clean, and ready. Every item on this checklist must be confirmed before the repo is submitted.

**Checklist — run each item and confirm:**

Repository hygiene:
- `git status` shows no uncommitted changes
- `.gitignore` is committed and `.env` is not tracked
- No `__pycache__/`, `.pytest_cache/`, or `.pyc` files are committed
- No test fixture data or personal files are committed

Functionality:
- `pip install -r requirements.txt` completes cleanly on a fresh virtualenv
- `python retriever.py` prints setup validation success for 7 policies and 14 cases
- `python agent.py` processes CASE-001 and prints raw JSON output cleanly
- `python validator.py` processes CASE-001 (APPROVE expected) and CASE-013 (ESCALATE expected) and prints clean formatted output for both
- `python evaluate.py` runs all 14 cases and prints the full metrics report with no errors
- `pytest tests/ -v` passes all tests with exit code 0

Output correctness:
- Every case in the evaluation output has a decision (no blank or null decisions)
- At least 3 of the 4 ambiguous cases are ESCALATE in the evaluation output
- At least 6 of the 8 straightforward cases are NOT ESCALATE in the evaluation output
- Both edge cases are ESCALATE in the evaluation output

Document completeness:
- `design.md` has all four sections and is between 300–500 words
- `README.md` has all required sections and every command in it works
- `policies.md` has 7 policies, each with all four fields
- `cases.json` has 14 cases, all validating against the `Case` model

Security:
- `grep -r "ANTHROPIC_API_KEY" .` returns only `.env.example`, `config.py`, and `README.md` — never a hardcoded value in any other file
- `cat .env` is never run in any script (API key is never printed to stdout)

**Dependencies:** All prior milestones and tickets.

**Definition of Done:**
- Every checklist item above is confirmed ✓
- The project is ready to submit

---

*End of Part 2 — Milestones 4 through 6*
*Full Build Plan complete. All 6 milestones, 22 tickets documented.*
