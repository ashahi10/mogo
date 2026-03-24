policy_id:
POL-001
title:
Identity Verification Required
rule:
If identity_verified is false, then deny the payout request. If identity verification status is unknown, null, or missing, then escalate for human review before any approval or denial is issued.
escalation_note:
Escalate if verification exists but is stale, inconsistently sourced, or marked as low-confidence by the verification provider.
---
policy_id:
POL-002
title:
Verified Name and Account Holder Match
rule:
If account_holder_name does not match verified_name and payout_amount exceeds 500 USD, then deny the payout request. Exact name alignment is required for payouts above this threshold.
escalation_note:
Escalate when the mismatch may be a minor variation, such as initials, abbreviations, punctuation differences, or hyphenation that could still represent the same person.
---
policy_id:
POL-003
title:
Large Payout Threshold Controls
rule:
If payout_amount exceeds 10,000 USD, then escalate for mandatory human review regardless of other pass signals. If payout_amount is between 5,000 and 10,000 USD inclusive and any additional risk indicator is present, then escalate.
escalation_note:
Escalate when the amount appears borderline due to rounding, split-payment structures, or uncertain currency normalization.
---
policy_id:
POL-004
title:
High-Risk Flag Override
rule:
If high_risk_flag is true, then escalate the case for human review. This condition cannot be overridden by identity verification, name match, account age, or low payout amount.
escalation_note:
No direct deny path applies under this rule; all flagged cases are escalated for specialist adjudication.
---
policy_id:
POL-005
title:
Profile Change Velocity Protection
rule:
If recent_profile_changes is 3 or more within a 24-hour window, then deny the payout request due to potential account takeover behavior. If recent_profile_changes is exactly 2 within 24 hours, then escalate for manual verification.
escalation_note:
Escalate when profile changes cluster around payout initiation and legitimate customer activity cannot be confidently distinguished from suspicious behavior.
---
policy_id:
POL-006
title:
New Account Payout Restriction
rule:
If account_age_days is less than 30 and payout_amount exceeds 500 USD, then deny the payout request. If account_age_days is between 30 and 60 and payout_amount is between 500 and 2,000 USD, then escalate for review.
escalation_note:
Escalate when account age is close to threshold boundaries or when account lifecycle metadata appears inconsistent across systems.
---
policy_id:
POL-007
title:
Missing Critical Data Handling
rule:
If missing_fields includes identity_verified, payout_amount, account_holder_name, or verified_name, then escalate because a governed decision cannot be made safely. If only non-critical fields are missing, then decisioning may proceed with heightened caution.
escalation_note:
Escalate when field completeness is uncertain or when conflicting records suggest that missing field declarations may be incomplete.
---
