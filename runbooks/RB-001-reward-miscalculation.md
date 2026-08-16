# RB-001 — Incident Runbook: Reward Miscalculation

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | C (Runbooks) — derived from Track A code |
| System | Profiles/Rewards, Checkout (`app/services/rewards.py`, `app/routers/checkout.py`) |
| Source of truth | `app/services/rewards.py`, `app/models.py` (`RewardLedgerEntry`, `Order`) |
| Governing design decision | ADR-001, *Reward Points Calculation and Storage* (Option C — immutable ledger) |
| Executable invariant | `tests/test_reward_ledger.py` |
| Related regression coverage | `tests/regression/test_track_b_regression_agent.py` (§1, items 7–10, 12) |
| Status | Draft — pending human sign-off (see §9) |
| Generated | AI-drafted from repository state; requires named domain-validation owner before use in production (see §9) |

## 1. Purpose and scope

This runbook covers **reward miscalculation**: any observed state in which a
customer's displayed or usable point balance does not match the balance the
system is supposed to derive, or in which points were earned, redeemed, or
reversed in an amount inconsistent with the rules in ADR-001.

It does **not** cover cart pricing errors upstream of checkout, fulfillment
state errors, or payment failures — those are separate verticals with their
own owners (day-one contract, §2).

## 2. The correctness model this incident violates

ADR-001 commits the system to one invariant, stated once and enforced nowhere
else:

```
balance(customer) == SUM(reward_ledger.points WHERE customer_id = customer)
balance(customer) >= 0
```

There is no stored balance column. `current_balance()` in `rewards.py`
computes this sum on every read. **A reward miscalculation is, by
construction, either a bad row in `reward_ledger` or a missing row that should
be there** — never a stale cache, because no cache exists. This framing
should drive every diagnostic step below: don't look for a balance to
"resync," look for the ledger row that is wrong or absent.

## 3. How this incident is likely to be reported

- A customer disputes their points balance or an applied discount.
- A checkout discount does not match `points_redeemed * $0.01` (the
  `CURRENCY_PER_POINT` conversion in `rewards.py`).
- `tests/test_reward_ledger.py` or the Track B regression suite fails on a
  balance-invariant assertion (`test_balance_equals_signed_ledger_sum`,
  `test_redemption_cannot_drive_balance_negative`).
- The `pragma: no cover — invariant guard` `RuntimeError` in
  `app/routers/checkout.py` (`"Ledger invariant violated: balance negative
  after checkout"`) appears in application logs. Treat this as a page, not a
  warning — it means the redemption lock or the balance check was bypassed.
- A customer support agent reports a balance that goes negative after an
  order cancellation.

## 4. Immediate triage

1. **Identify the customer(s) and order(s) involved.** Every ledger entry
   carries `customer_id` and `order_id`; every entry has a `reason` string
   for provenance (day-one contract §2.1).
2. **Pull the full ledger for the customer**, oldest first:
   ```python
   rewards.ledger_for_customer(session, customer_id)
   ```
   This is the audit trail ADR-001 §4 promises Track C. Read it before
   forming a hypothesis.
3. **Recompute the balance independently** and compare to what the
   application displayed:
   ```python
   rewards.current_balance(session, customer_id)
   # cross-check: sum(e.points for e in ledger_for_customer(session, customer_id))
   ```
   If these two numbers disagree with each other, the bug is in
   `current_balance()` itself or in a direct SQL path that bypassed it — treat
   as Sev-1 (§7), since it means the invariant computation is untrustworthy
   everywhere, not just for one customer.
4. **Do not manually edit `reward_ledger` rows to "fix" a customer's balance.**
   The table is append-only by design (`RewardLedgerEntry` docstring, and the
   `uq_ledger_one_earn_per_order` / `uq_ledger_single_reversal` constraints).
   A corrective entry must be appended through `rewards.py`, never a
   `DELETE`/`UPDATE`, or the audit trail this runbook depends on is destroyed
   for the next incident.

## 5. Root-cause map

Each candidate cause below is tied to a specific place in the code, so
diagnosis is a lookup, not a guess.

### 5.1 A caller wrote to `reward_ledger` outside `rewards.py`
The module docstring states this is the one thing that must never happen:
"Nothing outside it should write to `reward_ledger`." Check for any
`session.add(RewardLedgerEntry(...))` call outside `app/services/rewards.py`.
This is the highest-priority check because every other guarantee in this
runbook assumes it's false.

**Check:**
```
grep -rn "RewardLedgerEntry(" app/ --include=*.py | grep -v app/services/rewards.py
```

### 5.2 Concurrent redemption raced past the lock
ADR-001 §1 force 2: two concurrent redemptions can each read the same
starting balance and each append a negative entry, driving the balance below
zero. The mitigation is `lock_customer_for_redemption()`, which relies on:
- SQLite: `BEGIN IMMEDIATE` configured in `app/db.py` (`_begin_immediate`),
  which must fire on **every** engine used by the running process — including
  any second engine/connection string spun up for testing, scripts, or a
  live-smoke run (`scripts/track_b_live_smoke.py`).
- PostgreSQL/MySQL: `SELECT ... FOR UPDATE` on the customer row.

**Check:** Confirm `isolation_level=None` and the `connect`/`begin` event
listeners in `app/db.py` are actually attached to the engine that served the
request (a mis-pointed `COFFEE_DB_URL` or a second ad-hoc engine elsewhere in
the process would silently skip this). Look for two `redeem` entries against
the same customer with overlapping `created_at` timestamps that together
exceed a balance that was never that high.

### 5.3 The redemption cap was bypassed
`points_for_discount_cap()` limits redemption to the order's subtotal, and
the checkout router rejects (422) a redemption above that cap **before**
calling `rewards.redeem_points`. If a discount exceeds subtotal, either this
check was skipped on some code path, or the `ck_order_discount_within_subtotal`
constraint should have fired at the database layer and didn't — check whether
that constraint actually exists on the live database (`orders` table check
constraints), not just in `models.py`.

### 5.4 The earn/discount arithmetic constant was changed
`POINTS_PER_CURRENCY_UNIT` (1 point/$1) and `CURRENCY_PER_POINT` ($0.01/point)
are the only two knobs that determine earn and redemption value. Track B's
regression report (§6) demonstrated this exact failure by hand: changing
`CURRENCY_PER_POINT` from `0.01` to `0.02` produced a $2.00 discount where
$1.00 was expected, and the regression suite caught it. If a miscalculation
report matches "discount is 2x (or some other multiple of) expected," diff
these two constants against the last known-good commit first — it is the
cheapest check and has a precedent of being the actual cause.

### 5.5 Points were earned on the wrong amount
Points are earned on `subtotal`, not on the post-discount `total`
(`checkout.py` comment: "Earned on the pre-discount subtotal... the
alternative is equally defensible and must not be inferred from the
arithmetic"). If a report says "I earned more/fewer points than I expected
for this order," confirm which base the customer expected against
`order.subtotal` — this is a policy fact, not a bug, but it is exactly the
kind of "structurally correct, semantically surprising" gap this project's
methodology exists to surface (README §1). Escalate to Track A/D as a
requirements clarification if the reporter's expectation is reasonable and
undocumented in `docs/requirements/requirements-profiles-rewards-checkout.md`.

### 5.6 Cart subtotal drift (cross-vertical, not a rewards bug)
Checkout does not recompute the cart subtotal — it earns points on whatever
`cart_client.get_cart()` returns (`checkout.py` comment; day-one contract
§4.1 Q1). If `subtotal` ever comes to include tax or fees without the Rewards
vertical being told, reward accrual changes with **no change to
`rewards.py` at all**. Before concluding the bug is in Rewards, confirm what
the Cart vertical's `subtotal` field currently represents and whether that
matches the day-one contract's Q1 answer.

### 5.7 Cancellation reversal was never triggered
`cancel_order()` / `POST /orders/{order_id}/cancel` correctly reverses every
ledger entry for an order when called — but **nothing in the system calls it
automatically**. The day-one contract (§4.1, Q5) records this as an
unresolved question: "Who calls the reward reversal — Fulfillment, or
Checkout on notification? ... Until this is answered, cancelled orders keep
their points." If a customer's order shows `cancelled` but their ledger has
no `reverse` entries for it, this is very likely the cause, and it is a known
gap rather than a new defect — check whether `docs/comms/day-one-contract.md`
§4.1 item 5 has since been signed off; if not, this incident is evidence it
needs to be.

**Check:**
```python
entries = rewards.ledger_for_customer(session, customer_id)
earns_by_order = {e.order_id for e in entries if e.type == LedgerEntryType.EARN}
reversed_orders = {e.order_id for e in entries if e.type == LedgerEntryType.REVERSE}
# orders in earns_by_order but not reversed_orders, where order.status == CANCELLED,
# are un-reversed earns.
```

### 5.8 The open policy question materialized: negative balance after earn-reversal
`rewards.py`'s trailing comment and the `xfail`-marked test
`test_balance_never_negative_after_earn_reversal` document a real, currently
unresolved gap: if a customer earns points on order X, spends them on order
Y, and X is later cancelled, reversing X's earn can drive the balance
negative. This is **not a code defect** — the ledger arithmetic is correct —
it is an undecided product policy (allow transient negative and block further
redemption; reverse only down to zero; or claw back Y's discount). If
diagnosis lands here:
1. Confirm the sequence matches the pattern (earn → redeem elsewhere →
   reverse the original earn).
2. Do **not** silently patch the ledger to force non-negative. Escalate to
   the Track A owner to resolve via the requirements spec (new `R-R4`) per
   the note at the foot of `rewards.py`.
3. Record the incident against this known gap rather than opening a new
   defect, and check whether the `xfail` in `tests/test_reward_ledger.py`
   has since been resolved — if the policy has been decided, that test
   should no longer be `xfail`, and its continued `xfail` status is itself a
   process gap.

### 5.9 Double-earn or double-reversal
Both are structurally prevented at the schema layer:
`uq_ledger_one_earn_per_order` (partial unique index on `order_id` where
`type = earn`) and `uq_ledger_single_reversal` (unique on
`reverses_entry_id`). A double-earn or double-reversal report therefore
implies either the constraint is missing on the live database (schema drift
from `models.py`) or a retried request produced two *different* orders for
one logical checkout (a Cart/Checkout idempotency issue upstream of Rewards,
see day-one contract §4.1 Q2–Q3).

## 6. Diagnostic checklist (run in order)

1. Pull the full ledger for the affected customer (§4.2).
2. Recompute balance from the ledger by hand; compare to `current_balance()`
   output (§4.3).
3. Run `pytest tests/test_reward_ledger.py -v` against a copy of the
   affected data if feasible, to confirm the invariant suite still passes in
   general (a general failure implies a code regression, not a one-off data
   issue).
4. Check the constants (§5.4): `POINTS_PER_CURRENCY_UNIT`,
   `CURRENCY_PER_POINT` in `app/services/rewards.py`, against the last known
   good version.
5. Check for un-reversed earns on cancelled orders (§5.7) — the most likely
   cause given it is a documented, currently-open gap rather than a
   hypothetical one.
6. Check for writes to `RewardLedgerEntry` outside `rewards.py` (§5.1).
7. Check whether the order's subtotal basis matches customer expectation and
   the day-one contract's cart-subtotal definition (§5.5, §5.6).
8. If none of the above resolve it, check for a concurrency race (§5.2) by
   examining timestamps of near-simultaneous `redeem` entries for the
   customer.

## 7. Severity and escalation

| Condition | Severity | Action |
|---|---|---|
| Single customer, single order, ledger internally consistent, discrepancy traced to a documented policy gap (§5.5–§5.8) | Sev-3 | Log against the known gap; no code change; customer-support resolution per current policy |
| Single customer, ledger shows a missing reversal or a clearly wrong entry, root cause identified in §5 | Sev-2 | Append corrective ledger entry through `rewards.py` functions only (never edit rows directly); notify Track A owner |
| `current_balance()` disagrees with a manual re-sum for *any* customer, or the `checkout.py` invariant-guard `RuntimeError` fires in production | Sev-1 | Treat the redemption path as untrusted; consider pausing redemption (not earning) until the concurrency/lock path (§5.2) or the write-bypass path (§5.1) is confirmed closed; page Track A owner and Track D (governance) |
| Constraint (`ck_ledger_*`, `uq_ledger_*`, `ck_order_discount_within_subtotal`) missing on the live schema | Sev-1 | Schema drift from `app/models.py`; treat as a deployment defect, not a data incident |

## 8. Containment options while root cause is confirmed

- **Pause redemption, not earning.** Earning a positive entry can never
  violate the non-negative invariant under any interleaving
  (`lock_customer_for_redemption` docstring). Redemption is the only path
  that can drive the balance negative, so it is the only path that needs to
  be gated shut during a Sev-1.
- **Do not roll back or truncate `reward_ledger`.** It is the incident's own
  audit trail; destructive action here removes the evidence needed to close
  the incident and to write the postmortem's corrective-entry chain.
- **Corrective entries are `reverse` or `earn`/`redeem` rows appended through
  `rewards.py`, never row edits.** This keeps the ledger's append-only
  guarantee — and this runbook's diagnostic method — valid for the next
  incident.

## 9. Known limitations of this runbook (carry forward per README §1)

- This runbook was derived from the current state of the repository, not
  validated against a production incident. Per ADR-001 §5's own finding about
  AI-assisted artifacts, it should be reviewed and signed off by a named
  accountable owner (the Track A owner, per the increment log's Track C row)
  before being treated as authoritative.
- §5.7 and §5.8 describe **currently open, unresolved gaps** in the system
  (day-one contract §4.1 item 5; the `xfail` test), not hypothetical failure
  modes. This runbook will go stale the moment either is resolved — the
  resolution must be reflected here, not just in the ADR/requirements docs.
- Track B's regression suite (`tests/regression/test_track_b_regression_agent.py`)
  covers reward calculation and redemption bounding but, per its own report
  §7, has not been validated as a production release gate. A reward
  miscalculation that only appears in production should be added back to
  that suite once diagnosed here (increment log §2, Track C row: "identify
  flows not covered by Track B").

## 10. Closure criteria

An incident against this runbook is closed only when, for every affected
customer:

```
current_balance(customer) == SUM(reward_ledger.points WHERE customer_id = customer)
current_balance(customer) >= 0
```

is re-verified after any corrective entries, and the root cause is recorded
against one of §5.1–§5.9 (or logged as a new, previously unseen cause and fed
back into this runbook).
