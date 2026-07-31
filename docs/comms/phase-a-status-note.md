# Phase A Status Note — Track A (Profiles/Rewards, Checkout)

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Issued by | Allan — Track A, Profiles/Rewards and Checkout |
| Date | 2026-07-30 |
| Covers | Step 1 (scaffold and contract) and the Step 4 starting point |

---

## 1. To the group — what is done

The Track A scaffold is in the repository and runs. Six planning documents are
filed under the structure the README specifies, and there is now a working
application skeleton behind them, so the later stages have something real to
attach observations to rather than a design on paper.

**Documents filed**

| Document | Location |
|----------|----------|
| Interface contract (day-one contract) | `docs/comms/day-one-contract.md` |
| ADR-001 — reward points calculation and storage | `docs/adr/ADR-001-reward-points-calculation-and-storage.md` |
| Requirements specification with AI-assumption gap log | `docs/requirements/requirements-profiles-rewards-checkout.md` |
| Increment and coordination log | `docs/comms/increment-log.md` |
| Gen-AI observation record | `research/ai-logs/gen-ai-observation-record.md` |

**Code delivered**

A FastAPI application with SQLite via SQLAlchemy, covering the schema, the
reward ledger, and checkout. Seven endpoints exist; nine tests pass. Run it
with `pip install -r requirements.txt`, then `uvicorn app.main:app --reload`;
the API contracts are browsable at `/docs`.

**The architecture decision, in one paragraph.** ADR-001 is accepted, and its
conclusion is worth knowing even if you are not on Track A: there is no stored
reward-points balance anywhere in the system. The balance is the signed sum of
an append-only ledger, computed when read. That choice makes cancellation an
ordinary ledger entry rather than a separate reversal path, and makes concurrent
redemptions safe because entries are appended rather than a shared counter
mutated. The costs — a read-time computation and one extra table — are
acceptable at this scale.

**The research finding attached to it.** ADR-001 Section 5 records what happened
when the design question was put to a gen-AI tool without naming the
reversibility and concurrency constraints. The tool returned a confident,
well-structured answer centred on a stored mutable balance and did not raise
either constraint until it was asked directly. The output was not wrong in any
way that inspection would reveal; it was complete-looking and silently missing
the two concerns that turned out to decide the question. This reproduces, on an
unrelated system, the pattern recorded earlier in the moderation-framework
observation — which is what makes it a finding rather than an anecdote.

**Status: not yet unblocked.** The day-one contract is drafted but unsigned.
Parallel implementation on Track A does not begin until it is.

---

## 2. To the Track A teammate (Cart, Fulfillment)

The full kickoff is in `docs/comms/kickoff-message.md`. The short version:

**What is waiting on you.** Section 4 of the day-one contract has two sign-off
boxes — schema fixed, contracts fixed — and neither of us should start building
until both are ticked. I have added Section 4.1: six questions I could not
answer alone. Answer those and signing is a formality.

**What I built that touches your half.** `app/models.py` contains `carts`,
`cart_items` and `fulfillments`. They are there only so the database builds and
the foreign keys resolve — replace them freely. The fields named in contract
Section 2 are the part I actually depend on; changing those needs notice.

I also added three fields beyond the contract's table, documented with reasoning
in Section 2.1: `orders.subtotal`, `reward_ledger.reverses_entry_id`, and
`reward_ledger.reason`.

**Three questions that matter more than the others:**

1. *Is the cart subtotal goods-only, or does it include tax and fees?* I never
   recompute pricing — I earn reward points on whatever number you hand me. If
   the meaning of that number changes later, reward accrual changes with it and
   nothing in my code will look wrong. This is the one most likely to bite us.

2. *On cancellation, who triggers the reward reversal?* I have implemented it
   (`POST /orders/{order_id}/cancel`), but nothing calls it yet. Until we
   decide, a cancelled order keeps its points.

3. *Are the order states sufficient for ADR-002?* I have fixed `orders.status`
   at `confirmed`, `in_preparation`, `completed`, `cancelled`. Checkout writes
   only `confirmed`; the rest are yours. Adding a state after we both have data
   is a shared-schema change, so now is when it is cheap.

**What you can ignore.** The reward ledger is private to my vertical. You never
need to read or update a points balance — if something should change a
customer's points, it goes through my service and the ledger records it.

---

## 3. To Track B — Regression

**Delivered and testable now.** `POST /customers`, `GET /customers/{id}`,
`GET /customers/{id}/balance`, `GET /customers/{id}/ledger`, `POST /checkout`,
`POST /orders/{id}/cancel`. The OpenAPI document at `/openapi.json` is the
machine-readable contract; treat a diff in it as a change notice.

**The invariant to hold, stated once:**

> For every customer, at every observable moment, the balance equals the signed
> sum of that customer's `reward_ledger` rows, and is never negative.

There is no second definition of a balance anywhere in the codebase to disagree
with this one.

**Start from `tests/test_reward_ledger.py` rather than generating a suite from
the endpoint surface.** The invariant is a property of the ledger, and testing
it only through HTTP misses the reversal and idempotency cases. That file is a
starting point, not coverage — extending it is the useful work.

**Flows that must not break:** checkout completing; rewards calculating
correctly; redemption never driving a balance negative.

**One test is deliberately failing.** `test_balance_never_negative_after_earn_reversal`
is marked `xfail` against a genuinely undecided policy question — see Section 5.
Do not fix it. The decision has to be made in the requirements first.

**Notice schedule:** every endpoint delivery or change, naming the affected
flow. Increment 4 (redemption in checkout) will be flagged loudly.

---

## 4. To Track C — Runbooks

**The failure mode to write against, from ADR-001:** reward miscalculation — a
customer's displayed or redeemable balance not matching what the order history
warrants.

**What the code actually does, as against what the docs say.** Stated plainly,
because the gap between the two is your subject:

- The balance is derived on every read. There is no cached or stored value that
  can go stale, so "stale balance" is not a failure mode in this system.
- `GET /customers/{id}/ledger` returns the full ordered history. This is the
  audit trail: any balance can be reconstructed by hand from it, which is how a
  miscalculation claim gets adjudicated.
- Reversal entries carry `reverses_entry_id`, so the chain from an original
  entry to its reversal is explicit rather than inferred from timing.
- Points are earned on the pre-discount subtotal and floored, not rounded. A
  customer disputing a one-point discrepancy is most likely seeing the floor.
- A redemption exceeding the balance is rejected with a 409, not silently
  reduced. If a customer reports "it only used some of my points," that is a
  different bug and not this path.

**Known gap you should aim at.** There is an unresolved policy question
documented at the foot of `app/services/rewards.py` — reversing an earn whose
points have already been spent can leave a negative balance. Until it is
resolved, that is the most likely source of a real miscalculation incident.

**Coverage question for Track B:** ask them which of the reversal paths they are
not exercising. Those are where a runbook has the most value.

---

## 5. To Track D — Governance

**Design-decision record.** ADR-001 is accepted and is offered as the
design-decision artifact for this vertical. Section 5 records the AI-assisted
design interaction in full: the prompt as issued, what the tool contributed,
what it omitted, and what domain judgment was required to close the gap.

**Governance input, stated honestly:** this vertical contains no autonomous
action. Every earn is triggered by a user-initiated order placement; every
redemption is explicitly requested by the user at checkout; every reversal is
triggered by a user or staff cancellation. Nothing in the rewards or checkout
path acts on its own initiative or on a schedule. If your risk tiering has a
category for "no autonomous action, user-initiated only," this vertical sits in
it, and that claim is checkable against `app/services/rewards.py` — every
function that writes to the ledger is called from a request handler.

**The proposed conformance point from ADR-001 Section 5**, which is a governance
question as much as a technical one: acceptance of an AI-generated design
artifact should be gated by a named domain-validation step with a named
accountable owner, performed before the artifact is incorporated. The reasoning
is that the characteristic failure is not a detectable defect but a plausible,
complete-looking artifact with a silent omission. Conformance is therefore not
evidenced by the existence of an ADR, but by a recorded validation step inside
it — including which domain assumptions were checked, and by whom.

**One item requiring a governance decision, not a technical one.** The negative-
balance case in Section 4 above is a policy question with a customer-facing
consequence: whether a customer who spent points from an order that was later
cancelled keeps the benefit, loses it, or is left with a negative balance. It is
recorded as open rather than resolved in code, deliberately. It is the kind of
decision that should have an owner named before it is made by default.

---

## 6. What happens next on Track A

| Step | Activity | Status |
|------|----------|--------|
| 1 | Scaffold committed; day-one contract signed | Scaffold done; **signature outstanding** |
| 2 | TP.1 requirements stage, with AI-assumption gap log | Next |
| 3 | TP.2 architecture stage — ADR-001 | Complete |
| 4 | TP.3 implementation in increments | Skeleton in place; increments 1 and 3 substantially built |

Increment 4 — reward redemption landing in checkout — is the delivery to watch.
That is ADR-001's logic going live, and Tracks C and D both build on it.

## References

[1] ADR-001, *Reward Points Calculation and Storage.*
[2] Interface Contract — Track A Feature Verticals (`docs/comms/day-one-contract.md`).
[3] Increment and Coordination Log (`docs/comms/increment-log.md`).
