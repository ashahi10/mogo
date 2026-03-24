"""
Output validation module. Parses raw LLM response, validates against Pydantic
schema, retries on failure, and applies escalation override rules.
"""
