# Risk Assessment — Claude's Ability to Generate Incident-Response Runbooks

Assessment of the **AI agent and generation process**, based on the two
completed instances available: RB-001 (Reward Miscalculation) and RB-002
(Checkout Failing Under Load), plus the walkthrough report scoring both.

| Field | Value |
|---|---|
| AI system used | Claude |
| Task | Generate incident-response runbooks from code + docs alone |
| Instances assessed | RB-001, RB-002 |
| Evidence source | `RB-001-reward-miscalculation.md`, `RB-002-checkout-failing-under-load.md`, `runbooks-and-incident-response-report.md` |
| Assessor | Claude (self-assessment — see caveat in §8) |
| Date | 2026-08-19 |

---

## 1. Input completeness

Both runbooks name a "Source of truth" list in their header tables
(`rewards.py`, `checkout.py`, `db.py`, `models.py`, ADR-001, the day-one
contract, and relevant test files) — so the source set was defined and
disclosed, which is good practice. But both are generated from **static
text only**: nothing in either document indicates the code was actually
run, profiled, or traced at runtime. RB-002 in particular reasons entirely
from what the SQLite/SQLAlchemy configuration *should* produce, not from an
observed trace of what value actually reaches the driver.

**Rating: Medium.** Complete, disclosed source set; but static-only
analysis with no execution step is a structural constraint, and RB-002 is
the direct evidence of what that constraint costs.

---

## 2. Known LLM failure modes — check for each

- **Documentation-as-behavior conflation — Confirmed, RB-002.** RB-002 §2–§3
  builds its entire root-cause narrative around `PRAGMA busy_timeout` never
  being configured in `db.py`, reasoning from the *documented* SQLite
  default (`busy_timeout=0`) rather than tracing the actual `timeout` value
  passed through the code. Per the walkthrough report, the real defect is
  that a `timeout=0` value passed elsewhere does **not** propagate to the
  files that need it, and those files silently fall back to Python's own
  hardcoded `timeout=5.0` default. RB-002 never traces this propagation
  path — it reasons from what the config *looks like it should do* by
  reading `db.py`'s docstring and PRAGMA statements, not from following
  the actual value.
- **Confident tone masking an unverified claim — Confirmed, RB-002.** The
  runbook doesn't hedge this claim once. §2 states it as the dominant
  architectural fact ("This is the first thing to confirm or rule out"),
  §5.2 calls it "very likely the dominant cause," §6 step 5 says "almost
  certainly absent; treat as the first, cheapest fix to test," and §7/§8
  repeat it as the primary recommended mitigation and fix. Four separate
  restatements, all at the same high confidence, all resting on the same
  unverified inference.
- **Silent gap-filling — Confirmed, RB-001, but bounded.** §5.7 gives one
  fix for un-reversed cancellation earns without noting that a second
  cancellation path exists in the code that doesn't reverse points by
  design. Unlike RB-002, this wasn't stated with escalating confidence
  across multiple sections — it's a single omission in one subsection, and
  the sibling section (§5.8) explicitly does flag its own open question
  rather than resolving it. So the failure mode is present but narrower.
- **Uneven thoroughness across sections — Not observed as a distinct
  problem.** Later sections of both runbooks (severity tables, closure
  criteria) hold to the same specificity as earlier ones — this isn't
  where the risk showed up here.
- **No adversarial self-check — Likely, based on the output.** Nothing in
  either runbook's structure suggests the top-recommended cause was argued
  against before being finalized (e.g. no "alternative explanation
  considered and ruled out because..." note anywhere the primary cause is
  stated). RB-002's repeated, unhedged claim is consistent with a single
  generation pass with no self-critique step.

**Rating: High.** The most consequential failure mode — confident,
repeated, unverified causal claim — is directly present in one of the two
available instances, and it's the exact failure mode this assessment
exists to catch.

---

## 3. Verification performed against the AI's output

A walkthrough was performed for both runbooks (per the report) and it is
what caught the RB-002 defect — the process, not the generation, is where
this was actually caught. That's the control working as intended. But
note what verification depended on: a human (assisted by a second Claude
pass, per the report's §6 note) walking the incident through by hand,
against a written description of the codebase's actual timeout-handling
bug — not an automated re-check of the AI's claims against a running
system.

**Rating: Medium.** Verification happened and was effective, but it's
manual and single-pass; there's no evidence of a repeatable, automated
check that would catch the same class of error on the next runbook without
a human doing the same close read again.

---

## 4. Autonomy boundary

Both runbooks correctly declined to resolve open policy questions
themselves — RB-001 §5.8 explicitly routes the negative-balance question to
Track A rather than silently deciding it, and both carry
`Status: Draft — pending human sign-off` by default rather than
self-certifying. This boundary held in both instances, including in
RB-002, where the boundary held even though the *content* inside it was
wrong — a useful distinction: the process guardrail worked, the object-level
claim didn't.

**Rating: Low.** No autonomy overreach observed in either instance.

---

## 5. Task-fit

Runbook generation is checked before it's acted on (walkthrough, then
sign-off) rather than executing directly against production — the failure
mode is detectable before harm, which is the right shape of task to assign
here. The domain has a verifiable ground truth (the actual code), which is
what made the RB-002 error catchable at all. Consequence of an undetected
error is bounded — slower incident response, not irreversible harm,
provided the sign-off gate in §4 above is actually enforced and a bad
runbook doesn't skip straight to on-call.

**Rating: Low**, conditional on the sign-off gate being real and not
bypassed under incident-time pressure — a gate that's easy to skip
precisely when someone is in a hurry to resolve a live incident is a risk
this rating doesn't capture on its own.

---

## 6. Overall rating

| Category | Rating |
|---|---|
| 1. Input completeness | Medium |
| 2. LLM failure modes observed | **High** |
| 3. Verification performed | Medium |
| 4. Autonomy boundary respected | Low |
| 5. Task fit | Low |

**Overall risk tier: Tier 2 — Elevated / Use With Mandatory Verification**

Rationale: overall tier is driven by the worst category (§2), not the
average. One of two sampled instances contained a confidently-repeated,
unverified causal claim positioned as the primary fix — a failure mode
that, unmitigated, would actively misdirect an unfamiliar on-call
responder rather than merely slow them down. That is disqualifying for
unsupervised use on its own. It is not Tier 3 because the failure was
fully caught by the verification step that's already required before
sign-off (§3), the autonomy boundary held even inside the flawed runbook
(§4), and the task's blast radius is bounded by design (§5). This is a
generator whose independent output cannot yet be trusted, paired with a
verification step that, so far, has actually worked.

### Tier definitions used

| Tier | Meaning |
|---|---|
| Tier 1 — Low | Generate and route to sign-off with standard review; no elevated scrutiny needed. |
| **Tier 2 — Elevated** | **Generate only with mandatory, documented walkthrough against a simulated incident before sign-off; do not shortcut verification under incident-time pressure; re-run this assessment periodically as more instances accumulate.** |
| Tier 3 — High | Do not use for this task class without a change to the generation or verification process first (e.g. adding execution-based verification, not just static review). |

---

## 7. Decision

- [ ] Continue as-is
- [x] **Continue with changes:**
  1. Every runbook generation should be followed by an explicit
     self-critique pass — asking the model to argue against its own
     top-recommended cause — before the walkthrough, not as a substitute
     for it.
  2. Where a claim rests on "the config *should* produce X," the
     generation prompt should require that claim be traced to an actual
     execution or explicitly flagged as unverified, rather than stated at
     the same confidence as a traced claim.
  3. Track this failure rate over more instances than two before loosening
     this tier — n=2, with one instance showing a high-severity failure, is
     not enough data to be confident this is representative rather than
     noise.
- [ ] Stop using AI for this task class

---

## 8. Caveat on this being a self-assessment

This assessment was produced by Claude, evaluating Claude's own past
output. Section 3's rating already reflects one structural limit of that:
the most reliable check on my claims so far has been a human (with a
second, independent AI pass, per the report) actually reading the code
rather than my re-reading my own prior output. Treat this document itself
under the same rule it recommends for runbooks in §5 of the original
authorization request — draft, not authoritative, until a named human
reviews it against the actual codebase rather than against my summary of
it.
