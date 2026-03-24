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
policy_id:
POL-008
title:
Impossible Travel Detection
rule:
If impossible_travel_flag is true between recent authenticated events, then escalate for security review before payout release. If impossible travel appears alongside destination changes, deny until account control is re-verified.
escalation_note:
Escalate when geo telemetry confidence is low or VPN/proxy evidence introduces ambiguity.
---
policy_id:
POL-009
title:
Untrusted Device and New Session Risk
rule:
If device_trust_score is below 0.25 and payout_amount exceeds 1,000 USD, then deny pending re-authentication. If device_trust_score is between 0.25 and 0.40, escalate for adaptive verification.
escalation_note:
Escalate when device fingerprint quality is partial or recently reset.
---
policy_id:
POL-010
title:
Geolocation Mismatch Review
rule:
If geolocation_mismatch is true and recent_password_reset_hours is 24 or less, then escalate immediately for account takeover screening. If mismatch co-occurs with watchlist screening hit, deny and escalate to compliance.
escalation_note:
Escalate when location intelligence is derived from coarse network metadata only.
---
policy_id:
POL-011
title:
Credential Reset Cooling Window
rule:
If recent_password_reset_hours is 6 or less and payout_amount exceeds 500 USD, then deny until step-up verification completes. If reset occurred within 24 hours with low payout amount, escalate for analyst review.
escalation_note:
Escalate when reset timestamp source systems are inconsistent.
---
policy_id:
POL-012
title:
Payout Destination Change Controls
rule:
If payout_destination_recently_changed is true and payout_amount exceeds 1,500 USD, then deny pending beneficiary verification. If destination changed recently with amount below threshold, escalate for manual confirmation.
escalation_note:
Escalate when destination-change audit data is missing actor attribution.
---
policy_id:
POL-013
title:
Stale KYC Reverification
rule:
If kyc_age_days exceeds 365 and payout_amount exceeds 750 USD, then escalate for reverification before release. If kyc_age_days exceeds 730, deny until KYC refresh is completed.
escalation_note:
Escalate when jurisdictional policy for KYC staleness is uncertain.
---
policy_id:
POL-014
title:
Low KYC Confidence Safeguard
rule:
If kyc_confidence is below 0.50, then deny high-value payouts and escalate all cases for human review. If kyc_confidence is between 0.50 and 0.60, escalate regardless of payout amount.
escalation_note:
Escalate when confidence score provenance is unknown.
---
policy_id:
POL-015
title:
Watchlist Screening Guardrail
rule:
If sanctions_watchlist_hit is true, then escalate for compliance adjudication and block automatic approval. If a watchlist hit co-occurs with identity mismatch or payout destination changes, deny and escalate.
escalation_note:
Escalate when screening match quality cannot distinguish true positives from near matches.
---
policy_id:
POL-016
title:
Historical Payout Drift
rule:
If payout_amount exceeds three times historical_avg_payout and is above 1,000 USD, then escalate for anomaly review. If payout pattern drift exceeds five times baseline with concurrent risk signals, deny pending analyst confirmation.
escalation_note:
Escalate when historical baseline is unstable due to sparse account history.
---
policy_id:
POL-017
title:
Split Withdrawal Structuring Pattern
rule:
If transaction_velocity is 5 or more and multiple payouts occur just below internal manual-review thresholds, then deny for structuring risk. If structuring indicators are present but incomplete, escalate.
escalation_note:
Escalate when threshold windows overlap reporting intervals ambiguously.
---
policy_id:
POL-018
title:
Cross-System Data Conflict Policy
rule:
If data_conflict_flag is true across core identity or payout fields, then escalate because deterministic adjudication is unsafe. If conflicts involve beneficiary ownership and high payout amounts, deny pending reconciliation.
escalation_note:
Escalate when data recency ordering between systems cannot be trusted.
---
policy_id:
POL-019
title:
Composite Security Event Rule
rule:
If two or more of the following are true: low device trust, geolocation mismatch, recent password reset, destination change, then escalate immediately. If three or more are true and payout_amount exceeds 1,000 USD, deny and escalate.
escalation_note:
Escalate when one of the contributing signals is unavailable or unreliable.
---
