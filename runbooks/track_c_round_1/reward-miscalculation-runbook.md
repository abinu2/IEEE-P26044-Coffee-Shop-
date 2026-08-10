# Incident Runbook — Reward Miscalculation

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | C (Runbooks) — AI-generated incident-response runbook derived from Track A code |
| P26044 mapping | TP.6 (Operations / Incident Response) |
| Failure mode | Reward miscalculation |
| Codebase file under runbook | `app/services/rewards.py` (ADR-001, Option C implementation) |
| Supporting files | `app/models.py` (`RewardLedgerEntry`, `Order`), `app/routers/checkout.py`, `app/routers/customers.py`, `app/db.py` |
| Source of truth for correctness | ADR-001, Section 4 (the invariant); `tests/test_reward_ledger.py` |
| Primary consumers | On-call engineer, Track D (governance record of this incident class) |

---

## 1. Scope

This runbook covers incidents in which a customer's reward points balance, an
earned-points amount, or a checkout discount does not match what the system
should have produced under ADR-001. It does **not** cover fulfillment,
payment-processor failures, or cart pricing errors upstream of the subtotal
Checkout receives (see day-one contract, Section 4.1, Q1–Q2, for that seam).

The runbook assumes the reader has read access to the application database and
to the `/customers/{id}/ledger` and `/customers/{id}/balance` endpoints, but is
not necessarily a Track A contributor.

## 2. The invariant this incident violates

Every diagnostic step below reduces to checking one statement, stated once in
`rewards.py` and enforced nowhere else:

```
balance == SUM(reward_ledger.points WHERE customer_id = c)
balance >= 0
```

There is exactly one function that computes balance —
`rewards.current_balance()` — and exactly four functions that may write to
`reward_ledger`: `earn_points`, `redeem_points`, `reverse_entries_for_order`,
and (indirectly) `cancel_order`. A reward-miscalculation incident is, by
construction, either (a) one of those four functions producing a wrong entry,
(b) a write to `reward_ledger` that did not go through one of those four
functions, or (c) a caller (Checkout) supplying a wrong input — usually
`subtotal` — to a function that is itself correct.

## 3. Symptom categories

Triage the report into one of these before diagnosing. They point at different
code paths.

| Symptom | Customer-visible report | Likely code path |
|---|---|---|
| S1 — Balance doesn't match history | "My points don't add up" | `current_balance` vs. `ledger_for_customer` — should never disagree; if they do, this is a query bug, not a domain bug |
| S2 — Wrong points earned | "I got fewer/more points than expected" | `points_for_subtotal`, or `subtotal` passed into `earn_points` |
| S3 — Wrong discount amount | "100 points only took $X off, not $Y" | `discount_for_points`, `CURRENCY_PER_POINT` |
| S4 — Redemption accepted that shouldn't have been | Balance went negative | `redeem_points` balance check, or `lock_customer_for_redemption` |
| S5 — Redemption rejected that should have succeeded | 409 on a redemption within balance | Stale balance read, or a concurrent redemption that legitimately consumed it first |
| S6 — Cancelled order kept its points | Balance unchanged after cancellation | `reverse_entries_for_order` not called at all — see §5.4 |
| S7 — Cancelled order drove balance negative | Balance < 0 after a cancellation | The open domain question in §5.5 |
| S8 — Points awarded twice for one order | Duplicate earn entries | Should be prevented by `uq_ledger_one_earn_per_order`; see §5.6 |

## 4. Immediate triage (do this first, regardless of symptom)

1. **Pull the ledger, not the balance report.** `GET /customers/{customer_id}/ledger` returns every row, oldest first. This is the audit trail; treat the customer's or dashboard's reported number as a claim to be checked against it, not as ground truth.
2. **Recompute the invariant by hand.**
   ```
   sum(entry.points for entry in ledger) == current_balance   # must hold
   current_balance >= 0                                       # must hold
   ```
   If this fails, the incident is category (b) or (a) from §2 — a bad write, not a caller error — and you should stop triage and go to §5.6/§5.7 immediately, since it means the ledger itself is inconsistent, which is more serious than any single wrong entry.
3. **Identify the order(s) involved** and pull the `orders` row for each: `subtotal`, `discount_applied`, `total`, `status`. Confirm `discount_applied <= subtotal` (DB-enforced by `ck_order_discount_within_subtotal` — if this is violated, the row was written outside the checkout transaction, which should not be possible).
4. **Recompute expected values** using the same functions the code uses, not by re-deriving the arithmetic yourself:
   - Expected points earned: `points_for_subtotal(order.subtotal)` — floor, not round.
   - Expected discount for a redemption: `discount_for_points(points_redeemed)`.
   - Expected redemption cap: `points_for_discount_cap(order.subtotal)`.
5. **Check for a `reverse` entry chain** if an order was cancelled: every `earn`/`redeem` entry tied to that `order_id` should have exactly one `reverse` entry with `reverses_entry_id` pointing at it (enforced by `uq_ledger_single_reversal`).

## 5. Known failure modes, in order of likelihood

### 5.1 Discount conversion constant changed (S3)
`CURRENCY_PER_POINT` in `rewards.py` is the single source of the points→dollars
rate. Track B's regression report records that a change from `0.01` to `0.02`
was caught by the redemption regression test (100 points should discount
$1.00). If a miscalculation report matches "discount is exactly double/half
what it should be," check this constant first — it is a one-line diff to
verify or rule out.

### 5.2 Wrong subtotal reaching `earn_points` (S2)
`rewards.py` earns points on whatever `subtotal` Checkout passes it; it does
not question the number. Per the day-one contract, Section 4.1, Q1, whether
the cart's `subtotal` includes tax and fees is an **unsettled question between
verticals**. If earned points are consistently off by a fixed proportion
across many customers (not one), suspect that the Cart vertical's subtotal
definition changed without a corresponding contract amendment — this is a
cross-vertical integration defect, not a rewards defect, and should be
escalated to the Cart/Fulfillment owner and logged as a day-one contract
violation, not fixed inside `rewards.py`.

### 5.3 Floor-vs-round confusion (S2, false positive)
`points_for_subtotal` deliberately floors (`int(subtotal * 1)`), documented as
intentional: "awarding points for money not spent is the error direction that
compounds silently." A report of "I expected 5 points on a $4.99 order" is
**not a bug** — confirm this is the cause before treating it as an incident,
and close it as expected behavior with a pointer to this rule if so.

### 5.4 Cancellation doesn't reverse points (S6)
`reverse_entries_for_order` is correct and complete when it runs — but nothing
in the current codebase calls `cancel_order` automatically. Per day-one
contract, Section 4.1, Q5, *"who calls the reward reversal — Fulfillment, or
Checkout on notification?"* is explicitly listed as unanswered. If a customer
reports keeping points on an order they believe was cancelled, check whether
`POST /orders/{order_id}/cancel` was ever actually invoked for that order. If
it was not, this is not a code defect in `rewards.py` — it is the unresolved
integration question in the day-one contract, and the fix is a process/contract
fix (decide who triggers cancellation), not a patch to the reversal function.

### 5.5 Negative balance after reversing spent points (S7) — open domain question
This is the one failure mode the codebase documents as **known and
unresolved**, both in `rewards.py` (see the block at the foot of the file) and
in `tests/test_reward_ledger.py::test_balance_never_negative_after_earn_reversal`,
which is marked `xfail`. Sequence: a customer earns points on order X, spends
them on order Y, then X is cancelled. Reversing X's earn is arithmetically
correct — the ledger sum is still exactly right — but the resulting balance is
negative, because the points spent on Y no longer exist.

**This is not a bug to patch in isolation.** The ledger is behaving exactly as
designed; the policy question (allow a transient negative and block further
redemption, reverse only down to zero and absorb the loss, or claw back the
discount on Y) is explicitly left to the requirements spec (R-R2 or a new
R-R4) and has not been resolved as of this runbook. If this is the symptom:
1. Confirm it against the ledger (§4.2) — the sum will still equal the
   balance; only the sign is business-policy-wrong, not arithmetic-wrong.
2. Do **not** manually adjust the ledger to force a non-negative balance —
   that reintroduces the mutable-balance failure mode ADR-001 exists to
   eliminate, and destroys the audit trail.
3. Escalate to the Track A rewards owner to resolve the policy question and
   ship the decision as a code change with a corresponding requirement, not as
   an incident fix.
4. Log the incident count and pattern for Track D — this is the kind of
   AI-omitted design gap ADR-001 Section 5 documents, and a live occurrence is
   directly relevant governance evidence.

### 5.6 Duplicate earn for one order (S8)
Prevented by `uq_ledger_one_earn_per_order` (a partial unique index on
`order_id` where `type = 'earn'`). If duplicate earn rows are found in the
ledger, the constraint was bypassed — meaning a write happened outside
`rewards.earn_points`, most likely a direct `INSERT` against `reward_ledger`
or a retried checkout that reused a session across a rollback boundary
incorrectly. Treat this as a **schema-integrity incident**, not an arithmetic
one: identify the writer, and confirm no other table (`reward_ledger` is the
only one under ADR-001's write ownership) has similarly been bypassed.

### 5.7 Concurrent redemption race (S4, rare)
`redeem_points` calls `lock_customer_for_redemption` before reading the
balance. On SQLite, the serialization comes from `BEGIN IMMEDIATE` in
`app/db.py`, not from the lock function itself (which is a documented no-op
on that dialect). If a negative balance is observed following two
near-simultaneous redemptions:
1. Confirm the deployment's database is actually SQLite with the
   `BEGIN IMMEDIATE` event listener registered — if the app was pointed at
   Postgres/MySQL without deploying the `with_for_update()` path being
   exercised correctly, this is a configuration regression, not a `rewards.py`
   defect.
2. Confirm the balance check and the ledger append happened inside a single
   transaction (they must — `checkout.py` holds one transaction for the whole
   request; a refactor that split it would reopen the race named in ADR-001,
   Section 1, force 2).

### 5.8 Zero-point order treated as a missing entry (S2, false positive)
`earn_points` returns `None` and writes nothing for a sub-$1 subtotal. A
report of "no ledger entry for my $0.50 order" is expected behavior, not an
incident — confirm the subtotal before escalating.

## 6. Diagnostic decision tree

```
Report received
  │
  ├─ Does SUM(ledger) == reported balance?
  │     NO  → §5.6/§5.7 (integrity break) — escalate immediately, do not
  │           attempt a live fix without a second reviewer.
  │     YES → continue
  │
  ├─ Is the balance negative?
  │     YES → was it preceded by a cancellation of an order whose earned
  │           points were already spent?
  │             YES → §5.5 (known open policy question) — escalate, do not
  │                   patch the ledger.
  │             NO  → §5.6/§5.7 — integrity break, escalate.
  │     NO  → continue
  │
  ├─ Is the complaint about points *earned*?
  │     YES → check §5.2 (subtotal source) then §5.3 (floor, likely not a bug)
  │
  └─ Is the complaint about discount *amount*?
        YES → check §5.1 (conversion constant) first — cheapest check with
              highest hit rate per Track B's own fault-injection finding.
```

## 7. Remediation rules — what never to do

- **Never** `UPDATE` or `DELETE` a row in `reward_ledger`. The table is
  append-only by design (ADR-001, Option C); any correction is itself a new
  `reverse` (or corrective `earn`/`redeem`) entry with a `reason` explaining
  the incident, produced through `rewards.py`'s own functions or an
  equivalent reviewed script — never a raw statement against production data.
- **Never** add or write to a `balance` column, cached or otherwise, to
  "fix" a read-time cost or a display bug. ADR-001, Section 4 permits a
  materialized cache only if it is reconstructible from the ledger and never
  treated as authoritative.
- **Never** resolve a negative post-reversal balance (§5.5) by silently
  zero-flooring it in a query or in application code. That hides the sign of
  a real, unresolved policy question rather than answering it.
- **Do** resolve integration-boundary symptoms (§5.2, §5.4) at the contract
  level (day-one contract amendment, or a new requirement), not by adding
  compensating logic inside `rewards.py` that the ADR does not describe.

## 8. Post-incident verification

1. Re-run `pytest tests/test_reward_ledger.py` — the invariant suite must pass
   (the one deliberate `xfail`, §5.5, is expected and tracked, not a pass
   criterion to force).
2. Re-run the Track B regression gate (`scripts/run_track_b_regression.ps1`)
   and confirm the checkout/redemption/cancellation flows it names in
   `docs/track-b/regression-agent-report.md`, Section 1 (items 5, 6, 7, 10)
   still pass.
3. Re-check the invariant for the specific customer(s) involved: ledger sum
   equals reported balance, balance non-negative (or, for §5.5, that the
   negative balance is now the result of a *recorded, deliberate* policy
   decision rather than an open question).
4. Log the incident against the failure-mode ID (§5.1–§5.8) so recurrence
   rate is trackable — several of these categories (5.2, 5.4, 5.5) are
   currently *expected* to recur until the referenced open questions are
   closed, and Track D's governance record depends on that count being
   accurate rather than each occurrence being treated as a novel incident.

## 9. Escalation contacts

| Failure category | Escalate to |
|---|---|
| §5.2, §5.4 (contract ambiguity) | Track A rewards owner + Cart/Fulfillment owner jointly (day-one contract amendment required) |
| §5.5 (open policy question) | Track A rewards owner (requirements spec update, R-R2/R-R4) |
| §5.6, §5.7 (integrity/config) | Track A rewards owner + whoever owns the deployment's database configuration |
| Anything not covered above | Track A rewards owner, as `rewards.py` maintainer of record |

## References

[1] `app/services/rewards.py` — implementation and the open-question comment block at its foot.
[2] ADR-001, *Reward Points Calculation and Storage* (`docs/adr/ADR-001-reward-points-calculation-and-storage.md`).
[3] `tests/test_reward_ledger.py` — executable form of the invariant, including the tracked `xfail`.
[4] Interface Contract — Track A Feature Verticals (`docs/comms/day-one-contract.md`), Section 4.1, Q1 and Q5.
[5] Track B Regression Agent Report (`docs/track-b/regression-agent-report.md`), Sections 1 and 6.
