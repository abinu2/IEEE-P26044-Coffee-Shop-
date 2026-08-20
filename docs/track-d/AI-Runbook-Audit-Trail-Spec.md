# Audit Trail Spec — AI-Generated Runbook Decisions

Defines what gets logged every time Claude generates or revises a runbook,
and every time a human acts on that output. Purpose: make it possible to
answer, after the fact, "what did the AI claim, based on what, and what did
a human do about it" — without re-reading the whole runbook and guessing.
This spec exists directly because of a finding from the risk assessment: the
one failure that mattered (RB-002's `busy_timeout` claim) was caught by a
human walkthrough, not by anything self-checking. This trail is what lets
someone verify that check actually happened, instead of just trusting that
it did.

## 1. Scope

Logged: every runbook generation, every distinct causal/root-cause claim
inside it, every verification action, every human decision (sign-off,
rejection, revision request), and every status change a runbook goes
through afterward.

Not logged here: the runbook content itself (that's the artifact; this is
the record of what happened around it) or general chat/prompt text beyond
what's needed to reproduce a claim's origin.

## 2. Design principles

1. **One entry per decision point, not one entry per runbook.** A single
   runbook generation produces multiple loggable claims (RB-002 alone made
   at least four separate restatements of one causal claim — each is a
   candidate log entry, not just the runbook as a whole).
2. **Every AI claim records its confidence level and its basis, at
   generation time — not reconstructed later.** If this had been in place
   for RB-002, the log would show "confidence: high, basis: inferred from
   config/docstring, not traced" at generation time, which is the
   information a reviewer actually needs to decide how hard to check it.
3. **Every human action records what triggered it and what it changed.**
   A sign-off with no record of what was checked is not meaningfully
   different from no sign-off.
4. **The log is append-only.** Corrections are new entries referencing the
   old one, not edits to it — same principle as the reward ledger these
   runbooks describe (RB-001 §4.4): don't destroy the trail to fix the
   record.

## 3. Core entry schema

Every log entry, regardless of type, carries these fields:

| Field | Type | Description |
|---|---|---|
| `entry_id` | string | Unique ID for this entry. |
| `timestamp` | ISO 8601 | When the entry was recorded. |
| `runbook_id` | string | e.g. `RB-002`. |
| `event_type` | enum | See §4. |
| `actor` | string | Who/what produced this entry — `claude`, or a named human, or `system`. |
| `actor_role` | string | e.g. `generator`, `track-a-owner`, `verifier`, `on-call`. |
| `input_ref` | string/list | Pointer(s) to what this entry was based on — file paths + line ranges, a prior `entry_id`, or a described source (e.g. "SQLite documentation, general knowledge — not repo-specific"). |
| `summary` | string | One-line human-readable description of what happened. |
| `detail` | object | Event-specific payload — see §4 for what each event type carries. |

## 4. Event types

### 4.1 `GENERATION_STARTED`
Logged once, when a runbook generation task begins.

```json
detail: {
  "incident_scenario": "checkout failing under load",
  "sources_provided": ["app/db.py", "app/routers/checkout.py",
                        "app/services/rewards.py", "ADR-001",
                        "docs/comms/day-one-contract.md"],
  "execution_access": false,
  "prior_runbook_version": null
}
```

`execution_access: false` is itself an important field to log — it's the
single biggest factor the risk assessment identified (§1, Input
completeness) in why a claim like RB-002's went unverified at generation
time. Knowing at audit time that generation was static-only tells a
reviewer how much weight to give any claim from that run.

### 4.2 `CLAIM_MADE`
Logged for **every distinct causal or diagnostic claim** the runbook
states, at the point it's first made — not once per runbook.

```json
detail: {
  "claim": "Missing PRAGMA busy_timeout is the dominant cause of checkout failures under load",
  "location_in_runbook": "§2 point 3, restated §5.2, §6 step 5, §7, §8",
  "confidence_stated": "high — 'very likely the dominant cause', 'almost certainly absent'",
  "basis": "inferred from db.py's PRAGMA statements and SQLite's documented default busy_timeout of 0; not traced against an execution or a value-propagation check",
  "verifiable": true,
  "verified_at_generation_time": false
}
```

If the same underlying claim is restated in multiple sections (as in
RB-002), log it **once** with all locations listed in
`location_in_runbook` — the repetition itself is a fact worth capturing
(a claim restated four times at unchanged confidence is different from one
stated once), but it isn't four independent claims.

### 4.3 `GENERATION_COMPLETED`
Logged once generation finishes.

```json
detail: {
  "claim_count": 9,
  "unverified_high_confidence_claim_count": 1,
  "status_assigned": "Draft — pending human sign-off",
  "known_limitations_section_present": true
}
```

`unverified_high_confidence_claim_count` is derived directly from §4.2
entries and is the field a reviewer should look at first — it's what would
have flagged RB-002 for extra scrutiny before a human ever opened it.

### 4.4 `WALKTHROUGH_PERFORMED`
Logged when a human (or human + AI pair, per the original report's method)
walks the runbook through a simulated incident.

```json
detail: {
  "method": "manual walkthrough against simulated incident, cross-checked with a second Claude pass",
  "claims_checked": ["entry_id of each CLAIM_MADE entry reviewed"],
  "outcome_per_claim": [
    {"claim_entry_id": "...", "result": "confirmed"},
    {"claim_entry_id": "...", "result": "refuted",
     "correction": "actual cause is an unpropagated timeout=0 value; other modules fall back to a hardcoded 5.0 default, not busy_timeout"}
  ]
}
```

### 4.5 `CLAIM_REFUTED` / `CLAIM_CONFIRMED`
A focused entry per claim outcome, referencing the `WALKTHROUGH_PERFORMED`
entry it came from — kept separate from §4.4 so a reviewer can query
"show me every claim that was ever refuted" across all runbooks without
parsing walkthrough narratives.

```json
detail: {
  "claim_entry_id": "entry for the busy_timeout claim",
  "result": "refuted",
  "severity_of_error": "high — stated as primary fix across 4 sections; would misdirect an unfamiliar responder",
  "corrected_claim": "unpropagated timeout=0 causing fallback to Python's hardcoded 5.0 default"
}
```

### 4.6 `HUMAN_DECISION`
Logged for sign-off, rejection, or conditional approval — the point where
a named accountable person takes responsibility for the runbook's status.

```json
detail: {
  "decision": "reject",
  "reasoning": "top-recommended, repeated fix is factually wrong; would misdiagnose an unfamiliar responder before other steps eventually got them there",
  "blocking_claim_entry_ids": ["..."],
  "required_before_resubmission": "correct §2/§5.2/§6/§7/§8 to reflect the timeout-propagation cause; re-walkthrough"
}
```

Possible `decision` values: `approve`, `conditionally_approve`, `reject`.
A `conditionally_approve` entry must list `conditions` (mirrors §5 of the
risk-assessment template's decision section) as a sub-field.

### 4.7 `STATUS_CHANGE`
Logged whenever a runbook's status field changes for any reason — sign-off,
a code change invalidating it, a resolved "known limitation," or a real
incident revealing it was wrong in production.

```json
detail: {
  "from_status": "Draft — pending human sign-off",
  "to_status": "Revoked — superseded",
  "trigger": "code_change",
  "trigger_ref": "commit touching app/db.py timeout handling"
}
```

`trigger` enum: `sign_off`, `code_change`, `limitation_resolved`,
`production_incident_mismatch`, `revision_requested`.

### 4.8 `REVISION`
Logged when a runbook is regenerated/edited in response to a
`HUMAN_DECISION` or `CLAIM_REFUTED` entry.

```json
detail: {
  "responds_to_entry_id": "the rejection entry",
  "changed_claims": ["claim_entry_id(s) that were corrected"],
  "new_generation_entry_id": "the new GENERATION_STARTED entry, if fully regenerated"
}
```

A revision does not inherit the prior version's `HUMAN_DECISION` — it
re-enters the pipeline at §4.4 (walkthrough) before a new §4.6 entry can be
recorded, per the authorization request's rule that approval doesn't carry
forward across a revision.

### 4.9 `ON_CALL_USE` (post-approval)
Logged when a runbook is actually invoked during a real incident, distinct
from the walkthrough. This is what makes §4.7's
`production_incident_mismatch` trigger possible to detect.

```json
detail: {
  "incident_ref": "incident tracking ID, if one exists",
  "runbook_version_used": "commit/version hash of the runbook at time of use",
  "led_to_correct_root_cause": true,
  "notes": "free text — did any step mislead the responder even if the outcome was eventually correct?"
}
```

## 5. Who logs what

| Event type | Logged by |
|---|---|
| `GENERATION_STARTED`, `CLAIM_MADE`, `GENERATION_COMPLETED` | Claude, automatically, as part of generation — not reconstructed afterward by a human summarizing the output |
| `WALKTHROUGH_PERFORMED`, `CLAIM_REFUTED`/`CLAIM_CONFIRMED` | The human (or human+AI pair) performing the walkthrough |
| `HUMAN_DECISION` | The named accountable sign-off owner (Track A owner, per the authorization request §5) — not delegable to whoever ran the walkthrough, so the decision and the check remain separately attributable |
| `STATUS_CHANGE` | System-triggered where automatable (e.g. a CI hook on relevant file changes), human-triggered otherwise |
| `REVISION` | Whoever performs the revision, human or Claude |
| `ON_CALL_USE` | The on-call responder, as close to real-time as feasible, or reconstructed from the incident's own timeline immediately after |

## 6. Query patterns this should support

The schema is designed so these questions are answerable without reading
full runbook text:

- "Which runbooks currently have an unresolved high-confidence claim that
  was never walked through?" — join `GENERATION_COMPLETED.detail.unverified_high_confidence_claim_count > 0`
  against absence of a `WALKTHROUGH_PERFORMED` entry.
- "What's Claude's claim-refutation rate across all generated runbooks?" —
  count `CLAIM_REFUTED` / total `CLAIM_MADE`, the same signal used to set
  the risk tier in the risk assessment (currently 1 high-severity
  refutation in 2 sampled runbooks — too small an n to trust, per that
  assessment's §7, but this is the field that grows that sample over time).
- "Was this runbook ever used on-call while it had an unresolved
  known-limitation flag?" — join `ON_CALL_USE` timestamps against
  `STATUS_CHANGE` history for the same `runbook_id`.
- "Who approved a runbook that was later shown wrong in production?" —
  join `ON_CALL_USE.detail.led_to_correct_root_cause: false` back to the
  `HUMAN_DECISION` entry that approved that version.

## 7. Retention and access

- Retain indefinitely for any runbook that has reached `ON_CALL_USE` at
  least once — this is the record a postmortem needs.
- Draft-stage entries (never approved, never used) may be pruned after a
  defined window (e.g. superseded by 2+ revisions and never signed off),
  but the final `STATUS_CHANGE` to `Revoked`/`Superseded` is retained even
  if earlier detail entries are pruned.
- Readable by: Track A/B/C/D owners and on-call. Not editable by anyone
  after write, per §2 principle 4 (append-only).
