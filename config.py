"""Centralized configuration constants for Orion AI Decision Agent."""

import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env before reading any env-backed config.
load_dotenv()

# Anthropic model identifier used for decision generation.
MODEL_NAME = "claude-sonnet-4-5"
# Maximum number of tokens returned by the LLM response.
MAX_TOKENS = 1024
# Sampling temperature; low for stable policy-grounded outputs.
TEMPERATURE = 0.1

# Number of most relevant policies retrieved per case.
RETRIEVAL_TOP_K = 3
# Minimum confidence required to avoid deterministic escalation override.
CONFIDENCE_THRESHOLD = 0.65
# Minimum number of policy citations required in a valid model output.
MIN_POLICY_CITATIONS = 1

# Path to the static case dataset file.
CASES_FILE = "cases.json"
# Path to the policy source document.
POLICIES_FILE = "policies.md"

# Escalation rule toggle: escalate when required case data is missing.
ESCALATE_ON_MISSING_FIELDS = True
# Escalation rule toggle: escalate when retrieval returns no policies.
ESCALATE_ON_RETRIEVAL_FAILURE = True
# Escalation rule toggle: escalate after validation retry is exhausted.
ESCALATE_ON_VALIDATION_FAILURE = True

# API key used by Anthropic client; loaded from environment/.env.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print(
        "Warning: ANTHROPIC_API_KEY is not set. "
        "API calls will fail until you configure it in your environment or .env file.",
        file=sys.stderr,
    )
