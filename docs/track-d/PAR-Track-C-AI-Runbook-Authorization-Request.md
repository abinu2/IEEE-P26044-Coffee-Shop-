# Authorization Request — AI-Generated Incident-Response Runbooks

| Field | Value |
|---|---|
| Requesting party | Claude (AI agent), acting as Track C generator/reviewer |
| Requested by | Track C owner, on behalf of the coffee shop reference project |
| Date | 2026-08-08 |
| Artifacts covered | RB-001 (Reward Miscalculation), RB-002 (Checkout Failing Under Load) |
| Status | **Pending sign-off** — not yet authoritative |
| Related evidence | `runbooks-and-incident-response-report.md` (walkthrough findings) |

## 1. Purpose

This is a request for authorization to use AI (Claude) to generate, and to
continue maintaining, incident-response runbooks for this codebase from code
and documentation alone, and to define the conditions under which those
runbooks may be relied on operationally. This is a self-authorization
request in the sense that the AI that produced the artifacts is also the
party requesting approval to have them used — which is exactly why the
conditions below route final judgment to a named human, not back to the AI.

## 2. What I am requesting approval to do

- **Generate** incident-response runbooks from the current state of the
  repository (code, ADRs, requirements docs, day-one contract, regression
  suite) for incident classes selected jointly with Track A and Track B.
- **Walk through** each generated runbook against a simulated incident and
  report, in writing, whether it reaches the actual root cause or stalls on
  a plausible-but-wrong one.
- **Flag** — not silently resolve — any runbook step that describes what the
  code is *supposed* to do rather than what it *actually* does, per the
  known failure mode this track exists to catch.
- **Revise** a runbook after a walkthrough identifies a defect in it (e.g.
  correcting RB-002's `busy_timeout` framing), and resubmit the revised
  version through the same sign-off gate below — a revision does not carry
  forward the previous version's approval.

## 3. What I am not requesting, and am not approved to do

- I am **not** requesting authority to mark a runbook "authoritative" or
  production-ready myself. Every runbook I generate carries a
  `Status: Draft — pending human sign-off` line for exactly this reason, and
  that line stays until a named human removes it.
- I am **not** requesting authority to hand a runbook to on-call/support
  without the walkthrough step having been run and documented first. A
  runbook that has not been walked through against a simulated incident has
  no basis for anyone to trust it, including me.
- I am **not** requesting standing authority to resolve the open product/
  policy questions a runbook surfaces (e.g. RB-001 §5.7's cancellation-
  reversal ownership question, or §5.8's negative-balance policy gap). Those
  route to Track A/D as requirements clarifications, not to me.

## 4. Conditions under which a runbook may be used

A generated runbook may be treated as usable operational guidance **only
when all of the following hold**:

1. It has been walked through against at least one simulated incident, and
   the walkthrough result is recorded (root cause reached: yes/no, and
   where it broke down if no).
2. Any step later shown to be **factually wrong about the code's actual
   behavior** (as opposed to a documented open policy gap) has been
   corrected — not just noted as a caveat — before the runbook is handed to
   an unfamiliar engineer. A false claim repeated across multiple steps,
   as found in RB-002, is a blocking defect, not a limitation to footnote.
3. A named, accountable human owner (see §5) has reviewed the runbook and
   removed the "Draft — pending human sign-off" status.
4. The runbook's own "Known limitations" section is current — if a
   limitation it names has since been resolved elsewhere (a policy decided,
   a test un-`xfail`'d, a schema constraint added), the runbook has been
   updated to reflect that before reuse.

A runbook that fails any of these stays in draft status and is not routed
to on-call.

## 5. Sign-off

| Role | Responsibility | Sign-off required before |
|---|---|---|
| **Track A owner** (named accountable owner per increment log, Track C row) | Confirms the runbook's factual claims about code behavior are correct against the current codebase; owns any requirements clarification the runbook surfaces | Status changes from Draft to Approved |
| **Track B owner** | Confirms which incident-triggering flows are and aren't covered by the regression suite, so runbook scope reflects real test gaps rather than guesswork | Incident-scenario selection (§2, generation step) |
| **Track D (governance)** | Reviewed and notified for any Sev-1-class runbook (see RB-001 §7) or any runbook whose containment guidance touches a correctness-critical boundary (e.g. the checkout transaction) | Approval of any runbook carrying a Sev-1 path |
| **Track C owner** | Owns the walkthrough record, keeps runbooks current as their "known limitations" are resolved, and is the point of contact for on-call if a runbook is later found wrong in production | Ongoing, post-approval |

No runbook is handed to on-call support on the basis of my output alone.
The AI-generated draft plus the walkthrough result together form the
*input* to sign-off, not a substitute for it.

## 6. Basis for this request — findings so far

- **RB-001 (reward miscalculation):** walkthrough found one confirmed
  defect — step 5.7 gives one generic fix for cancellation but the codebase
  has two distinct cancellation paths, only one of which reverses points,
  and the runbook doesn't separate them. This is narrow enough (one path
  affected, rest of the runbook holds up, the gap is at least partially
  self-disclosed in the runbook text) that it is being requested for
  **conditional approval**: usable by a confident engineer today, needs the
  5.7 split fixed before being handed to on-call as-is.
- **RB-002 (checkout under load):** walkthrough found a defect that repeats
  across multiple steps and is presented as the primary recommended fix —
  the runbook attributes the failure to `busy_timeout`, but the actual
  mechanism is a `timeout=0` value not propagating and other modules
  falling back to a hardcoded `5.0` default. This is **not approved for use
  as-is**: an unfamiliar engineer following the runbook's most confident
  guidance would very likely misdiagnose the incident first. RB-002 must be
  corrected and re-walked-through before it goes back through §5 sign-off.

## 7. Review / revocation triggers

Approval for any individual runbook is automatically void, and it reverts
to Draft, if:

- The underlying code changes in the area the runbook covers (routers,
  services, or db config it cites), until re-verified against the new code.
- A "known limitation" the runbook names is resolved elsewhere but not yet
  reflected in the runbook text.
- A real incident shows the runbook's guidance led responders to the wrong
  cause, regardless of what the walkthrough found beforehand.
