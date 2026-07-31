# ADR-001 — Reward Points Calculation and Storage

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |
| Author | Allan |
| Implementation | `app/services/rewards.py`; invariant suite `tests/test_reward_ledger.py` |
| Feature vertical | Profiles and rewards; Checkout |
| Related decisions | ADR-002 (fulfillment state model) |
| Downstream dependents | Track B (regression invariant), Track C (failure-mode runbook), Track D (governance record) |

## 1. Context

Reward points accrue against a customer's order history, and checkout discounts
are derived from the available points balance. The decision recorded here
concerns two coupled questions: at which point in the order lifecycle points are
computed, and where the authoritative balance is held.

Three forces shape the decision:

1. **Reversibility.** An order may be cancelled or refunded after points would
   have been awarded. The balance model must remain correct across these events.
2. **Concurrency.** Two checkout operations for the same customer may redeem
   against a single balance concurrently. The model must not permit a balance to
   be double-spent or driven negative.
3. **Read frequency.** The balance is read on every checkout, to display the
   available discount, and written whenever an order completes or a redemption
   occurs.

The application operates at student scale, but the reversibility and concurrency
concerns are representative of the correctness properties a conformant
organization would be expected to have reasoned about, and are therefore treated
as first-order rather than deferred.

## 2. Options Considered

### Option A — Compute at order placement; persist a mutable balance

Points are added to a stored balance column when an order is placed.

*Assessment.* Reads reduce to a single-column lookup, and the model matches the
conventional loyalty-account pattern. However, because the persisted balance is
the source of truth, a cancellation or refund requires dedicated reversal logic
to restore correctness — a path that is easy to implement incompletely. The
balance is additionally a shared mutable counter, so concurrent redemptions may
race: two operations reading the same starting value can each commit a
redemption, producing a negative or double-counted balance.

### Option B — Compute at fulfillment; persist a mutable balance

As Option A, but points are awarded only once the order reaches the delivered
state.

*Assessment.* This removes the award-on-cancelled-order case, since cancelled
orders never reach fulfillment. It does not address the concurrent-redemption
race, which remains inherent to the mutable-counter model. It also introduces a
dependency on the fulfillment vertical for a rewards outcome, coupling two
otherwise independent features.

### Option C — Derive the balance from an immutable ledger

No balance is persisted. An append-only ledger records each earn, redeem, and
reversal event against an order. The current balance is computed on read as the
signed sum of ledger entries.

*Assessment.* The balance is correct by construction. Cancellation is expressed
as a reversing ledger entry rather than as a separate mutation path, eliminating
bespoke reversal logic. Concurrency is handled by appending entries and
validating redemption against the summed ledger within a single transaction,
rather than mutating a shared counter. The costs are a computation on each read,
which admits a later materialized-sum optimization, and the up-front design of
the ledger schema and event types.

## 3. Decision

**Option C is adopted.**

The two governing forces — reversibility and concurrency — are eliminated by the
ledger model's structure rather than mitigated by additional logic layered onto a
mutable balance. Options A and B present lower initial complexity, but once the
correctness properties in Section 1 are actually required, both accumulate
reversal handling and locking that exceed the ledger's total complexity. The
read-time computation cost is acceptable at the project's scale and has a known
optimization path that does not reintroduce a mutable source of truth.

## 4. Consequences

The redemption path validates available balance against the ledger sum inside a
single transaction; balances cannot be driven negative. Cancellation and refund
are handled uniformly as reversing entries. Track B receives a testable
invariant: the derived balance equals the signed ledger sum at all times and is
never negative. Track C receives an auditable event history against which a
reward-miscalculation incident can be diagnosed. Track D receives the fact,
recorded here, that no autonomous action exists in this vertical — every earn and
redemption is initiated by a user action or an order-state transition.

The principal cost carried forward is the read-time summation. Should it become
material, a materialized balance may be introduced, provided it is maintained as
a derived cache of the ledger and never treated as the authoritative value.
Ledger event types are fixed as `earn`, `redeem`, and `reverse`. The separable
question of whether earn occurs at placement or at fulfillment does not affect the
storage model and is recorded in the requirements specification.

## 5. Gen-AI Assisted Design Observations

This section records the gen-AI tool interaction through which the options in
Section 2 were developed, and the observation drawn from it. It is included
because the design of this artifact is itself an object of study for TP.2
(Architecture and Design): the concern is not only which option was selected, but
what the tool contributed, what it omitted, and what domain judgment was required
to reach a sound decision.

**Tool and model.** [e.g., Claude Opus 4.8] · **Date of interaction.** [YYYY-MM-DD]

**Initial prompt (as issued).**

```
[Paste the exact first prompt. The prompt issued for this record deliberately
withheld the reversibility and concurrency constraints, in order to observe
whether the tool surfaced them unprompted. Recommended form:

"I'm building a coffee ordering app. Customers earn reward points on orders and
can redeem them for discounts at checkout. How should I calculate and store the
reward points balance? Give me two or three options with trade-offs."]
```

**Observed response.** The tool returned a structured, confidently-presented
recommendation centered on a persisted mutable balance updated at order
placement — Option A above — with a clear articulation of its read-performance
advantage. The response was coherent and complete in presentation. [Adjust to
match the actual response received; record the option it defaulted to and the
structure it used.]

**What the tool contributed.** A usable scaffold of design options was produced
in seconds, providing a structured starting position rather than a blank page.
The read-performance trade-off of the mutable-balance model was stated accurately
and did not require correction.

**What the tool omitted.** Neither the reversibility case (points awarded against
an order later cancelled or refunded) nor the concurrent-redemption race appeared
in the initial response. The immutable-ledger model was not offered as an option
until these two constraints were named explicitly in a follow-up prompt, at which
point the tool represented the ledger approach accurately. The tool did not, at
any point in the initial exchange, flag that its recommendation rested on
unstated domain assumptions, nor did it indicate that the answer warranted
validation against the specific correctness requirements of a rewards system.
[Record the actual sequence; if the tool did surface a constraint unprompted,
state which and when.]

**Observation.** The tool's initial design output was calibrated to the modal
case in its training distribution — a conventional loyalty-points balance — and
was confidently structured around that case while silently omitting the
correctness concerns specific to this domain. The omissions were not visible as
errors; the artifact appeared finished. Recognizing that the reversibility and
concurrency constraints were absent, and that they were decisive, required domain
knowledge held by the practitioner rather than supplied by the tool. The
constraints could only be introduced into the exchange by a practitioner who
already knew to introduce them.

This reproduces, on an unrelated system, a pattern first recorded in an earlier
observation on AI-assisted design of a moderation dimension framework, in which a
tool-generated framework defaulted to generic social-media harm categories and
omitted a domain-critical category until the practitioner supplied it. The
present case is a second, independent instance: the failure mode is a
structurally coherent design artifact that omits a domain-critical concern rather
than one that is visibly incorrect, and its detection depends on domain expertise
applied as a validation step.

**Implication for the sub-process definition.** The observation supports a
specific requirement for the TP.2 sub-process: acceptance of an AI-generated
design artifact should be gated by a named domain-validation step with a named
accountable owner, performed before the artifact is incorporated. Because the
characteristic failure is a plausible, complete-looking artifact with a silent
omission rather than a detectable defect, the decision record for an AI-assisted
design should additionally capture which domain assumptions the output was
validated against, and by whom. Conformance for this sub-process is therefore
best evidenced not by the presence of an ADR alone, but by the presence of a
recorded domain-validation step within it.
