# Incident Runbook — Checkout Failing Under Load

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | C (Runbooks) — AI-generated incident-response runbook derived from Track A code |
| P26044 mapping | TP.6 (Operations / Incident Response) |
| Failure mode | Checkout failing under load (elevated latency, errors, or timeouts as concurrent checkout volume rises) |
| Codebase file under runbook | `app/routers/checkout.py` (`POST /checkout`, `POST /orders/{order_id}/cancel`) |
| Supporting files | `app/db.py` (engine/session/transaction configuration), `app/services/rewards.py`, `app/services/cart_client.py`, `app/main.py` |
| Source of truth for the design trade-off being exercised | ADR-001, Section 1 (force 2: concurrency); `app/db.py` module docstring |
| Primary consumers | On-call engineer, Track D (governance record — this failure class is a scale limit the design accepts, not a defect) |

---

## 1. Scope

This runbook covers incidents in which `POST /checkout` (and, secondarily,
`POST /orders/{order_id}/cancel`) shows degraded latency, elevated error
rates, or outright failures as concurrent request volume increases. It does
**not** cover reward-arithmetic correctness under normal load — see the
companion runbook, *Reward Miscalculation* — though §6.6 below explains how to
tell the two apart when a load incident produces a redemption rejection.

The runbook assumes the reader can read application logs/error responses and,
ideally, has shell access to the deployment to inspect the running process and
the SQLite database file.

## 2. The design fact this incident exercises

`POST /checkout` does not fail under load because of a bug in the checkout
logic. It fails because the persistence layer was deliberately built to
**serialize all writers**, and that choice was made to guarantee reward-ledger
correctness (ADR-001), not to guarantee throughput. `app/db.py` states this
directly:

> `BEGIN IMMEDIATE` on transaction start... closes the concurrent-redemption
> race... The cost is that all writers serialize, which is acceptable at this
> scale.

Two things follow that every diagnostic step below depends on:

1. **The lock is database-wide, not per-customer.** `BEGIN IMMEDIATE` is taken
   at the *start* of every transaction — before the cart is even read — and
   held until commit or rollback. A checkout for customer A and a checkout for
   customer B are not independent under load: B's request queues behind A's
   for the *entire* duration of A's transaction, even though ADR-001's
   concurrency concern only required serializing *redemptions against the same
   customer*.
2. **No `busy_timeout` is configured.** SQLite's default behavior when a
   writer cannot acquire the lock immediately is to raise `database is
   locked` rather than wait. Nothing in `app/db.py` sets a busy timeout, so
   under contention the failure mode is an immediate exception, not a queued
   request with graceful backpressure.

This is a genuine scale limit, correctly traded off for correctness at
"student scale" (README, Section 5; ADR-001, Section 1). A load incident here
is evidence the deployment has outgrown that scale assumption — it is not, on
its own, evidence that anything in `checkout.py` is wrong.

## 3. Symptom categories

| Symptom | Observed as | Points to |
|---|---|---|
| L1 — Rising p95/p99 latency on `/checkout`, no errors yet | Slow but successful checkouts | Global write-lock queueing (§4.1) — expected early-warning sign, not yet a failure |
| L2 — `sqlite3.OperationalError: database is locked` surfaced as 5xx | Checkout requests erroring under burst traffic | No `busy_timeout` (§4.2) |
| L3 — Elevated 502s from `/checkout` | "Cart unavailable" errors under load | `cart_client.CartUnavailable` (§4.5) — check whether the Cart vertical/read path is the actual bottleneck, not rewards |
| L4 — Elevated 409s ("Redemption of N exceeds available balance") under load specifically | Redemptions rejected that succeed when retried moments later | Expected serialization behavior (§4.1), not a miscalculation — see §6.6 to distinguish from the reward-miscalculation runbook |
| L5 — Requests hang rather than error | No response within client timeout | Lock wait with no `busy_timeout` and no client-side timeout either — see §4.2 |
| L6 — Single-process ceiling reached (CPU/latency flatlines regardless of DB) | Throughput plateaus well below expected capacity | Dev-mode single-process server (§4.3) |

## 4. Known contributing factors, in order of likelihood

### 4.1 Global write-lock serialization (primary factor)
Every `POST /checkout` and `POST /orders/{order_id}/cancel` call opens one
transaction that holds SQLite's write lock for its full duration — cart
validation, redemption check, ledger append, earn append, and commit — because
`app/db.py` issues `BEGIN IMMEDIATE` at transaction start rather than at first
write. Under concurrent load, checkout requests do not run in parallel; they
queue single-file behind whichever request currently holds the lock. This is
the expected, designed-in behavior at scale beyond what ADR-001's "student
scale" framing anticipated — confirm this is the dominant factor before
looking further by checking whether latency scales roughly linearly with
concurrent checkout volume (a signature of single-writer queueing) rather than
spiking irregularly.

### 4.2 No `busy_timeout` configured
Because no busy timeout is set on the SQLite connection, a writer that cannot
immediately acquire the lock does not wait and retry — it raises
`database is locked` right away. Under load this converts what would be
survivable queueing delay (§4.1) into outright request failures. This is the
single highest-leverage, lowest-risk mitigation available (see §7.1) because
it changes queueing behavior without touching the correctness-critical locking
strategy at all.

### 4.3 Single-process development server
`app/main.py`'s documented run command is `uvicorn app.main:app --reload` —
explicitly a development invocation (`--reload` is not used in production
deployments). No multi-worker or process-manager configuration
(`--workers N`, gunicorn, etc.) exists anywhere in the repository. If the
deployment under incident is still running the README's dev command, all
checkout traffic — including the CPU-bound parts (request parsing,
Pydantic validation, JSON serialization) — funnels through a single process.
**Note the interaction with §4.1**: adding more worker processes increases
concurrency at the application layer but does **not** relieve the SQLite
single-writer bottleneck, since every worker process still contends for the
same file-level write lock. Do not treat "add workers" as a full fix in
isolation — see §7.

### 4.4 Whole-checkout-in-one-transaction scope
`checkout.py`'s docstring is explicit that the entire handler runs in one
transaction "because the balance check and the ledger append that spends
against it must not be separated by a commit." That correctness requirement
is real and must be preserved (see §7's constraints), but it also means any
slow step inside the handler — notably the cart read via `cart_client.get_cart`
— extends how long every other checkout request queues behind it. If cart
reads are slow (e.g., the Cart vertical's implementation does extra work once
delivered), that latency is now paid by the *entire system's* checkout
throughput, not just by the customer whose cart was read.

### 4.5 Upstream cart-read failures surfacing as checkout failures
`cart_client.CartUnavailable` is raised whenever the cart cannot be read or is
not in an `open` state, and `checkout.py` converts this to a 502. Under load,
a spike in 502s from `/checkout` can be a *symptom of the Cart vertical*
straining, not of rewards/checkout logic. Before treating a 502 spike as a
checkout-under-load incident in this vertical, rule out the Cart side: check
whether the same load also correlates with cart-read latency or cart-service
errors independent of the checkout endpoint.

### 4.6 No rate limiting or ingress backpressure
Nothing in the application or the GitHub Actions workflow configures request
rate limiting, a queue depth cap, or a circuit breaker in front of `/checkout`.
Under a load spike, requests are accepted and immediately compete for the
single write lock (§4.1) rather than being shed or queued at the edge. This
means load incidents present as a wall of near-simultaneous lock failures
(§4.2) rather than a controlled degradation.

### 4.7 No load testing exists for this path
Track B's regression agent report is explicit that its scope is functional
regression, not load: item 3 of its "not ready to gate production" list is
*"the workflow is not connected to a real deployment pipeline yet,"* and
nothing in `tests/regression/test_track_b_regression_agent.py` or the CI
workflow exercises concurrent request volume. **There is no prior baseline for
"expected" checkout throughput** — do not assume a specific request-per-second
target is being violated; establish or ask for one as part of the incident
record if none exists.

## 5. Immediate triage

1. **Classify the failure mode**, not just the HTTP status. `database is
   locked` (§4.2), a generic timeout with no error body (§4.2/§4.4), and a
   502 from `CartUnavailable` (§4.5) point at different layers — pull actual
   exception text/log lines, not just status codes.
2. **Check whether latency degrades linearly or errors appear abruptly.**
   Linear degradation with volume is consistent with lock queueing alone
   (§4.1); a hard cliff into errors at a specific concurrency level is
   consistent with `busy_timeout` absence (§4.2) — the lock wait simply fails
   instead of queuing past a certain contention point.
3. **Confirm process topology.** Is the deployment running a single `uvicorn`
   process (§4.3), and is it the `--reload` dev invocation from the README?
4. **Rule out the Cart vertical as the actual source** (§4.5) by checking
   whether cart-read latency/error rate rose independently of checkout write
   volume.
5. **Confirm no partial writes occurred.** `checkout.py` wraps its transaction
   in try/except with `session.rollback()` on any exception — a failed
   checkout under load should leave **no** `orders` row and **no**
   `reward_ledger` row for that attempt. If partial rows are found (an order
   row with no matching earn entry, for instance), that is a distinct,
   more serious incident — the rollback path itself failed — and should be
   escalated separately from a pure load/availability incident.

## 6. Diagnostic decision tree

```
Report received: checkout errors/slowness under load
  │
  ├─ Are partial rows appearing (order without matching ledger entry)?
  │     YES → rollback-path failure — escalate as a code defect, not a load
  │           limit. Stop here; this is out of scope for this runbook.
  │     NO  → continue
  │
  ├─ Is the error "database is locked" / an SQLite OperationalError?
  │     YES → §4.2 (no busy_timeout) confirmed as proximate cause.
  │           §4.1 (global lock scope) is the underlying structural cause.
  │           → go to §7.1 and §7.2.
  │
  ├─ Are requests slow but eventually succeeding, no errors?
  │     YES → §4.1 alone (queueing, no timeout failures yet) — this is an
  │           early warning; capacity planning, not yet an outage.
  │
  ├─ Are 502s dominant?
  │     YES → check whether Cart-side latency correlates (§4.5) before
  │           attributing this to checkout/rewards at all.
  │
  ├─ Are 409s ("exceeds available balance") elevated specifically under load,
  │   with the same redemption succeeding on retry?
  │     YES → expected serialization behavior (§4.1), not a miscalculation.
  │           See §6.6 below before escalating as a rewards bug.
  │
  └─ Is throughput flat regardless of DB-layer symptoms?
        YES → check process count / CPU saturation on the single uvicorn
              process (§4.3).
```

### 6.6 Distinguishing a load-induced 409 from a reward miscalculation
Under heavy concurrent redemption traffic for the *same* customer, it is
correct and expected for a 409 to appear if a competing request already spent
the balance first — the ledger and the lock are doing exactly what ADR-001
requires. This is **not** the reward-miscalculation failure mode covered in
the companion runbook. Use this test: if the ledger, once inspected, shows the
rejected redemption would indeed have exceeded the balance *at the time the
losing request's transaction was serialized*, this is correct concurrency
behavior under load, not a miscalculation. Escalate as a miscalculation only
if the ledger sum disagrees with what should have been available.

## 7. Remediation — ordered by risk

Any remediation **must preserve** the property ADR-001 exists to guarantee:
the balance check and the ledger append it gates must remain inside one
transaction, and no reward miscalculation may be introduced in exchange for
throughput. Do not treat "checkout is failing under load" as license to loosen
locking; treat it as a scale problem to solve around that constraint.

1. **Set a `busy_timeout` on the SQLite connection (lowest risk, do first).**
   This converts hard lock failures (§4.2) into bounded waits, which is a
   strict improvement in survivability without touching correctness — a
   request that would have failed instantly now queues briefly instead,
   matching the serialization the design already assumes. This does not fix
   the underlying throughput ceiling (§4.1); it fixes the failure mode.
2. **Confirm production process configuration** — move off `uvicorn --reload`
   if that is what's deployed, and size workers appropriately. Do this
   understanding it does **not** relieve SQLite's single-writer limit (§4.3);
   it only removes the app-layer ceiling, so pair it with steps below rather
   than treating it as sufficient alone.
3. **Narrow the transaction's held-lock window** by moving anything that does
   not need write-lock protection (notably the cart read in
   `cart_client.get_cart`) earlier, outside the locked section, where the
   correctness argument in `checkout.py`'s docstring permits it. This
   requires care: only the balance-check-and-append sequence, not the whole
   handler, needs to be inside the lock per ADR-001's actual requirement —
   review with the rewards owner before changing transaction boundaries.
4. **If sustained load exceeds what a single-writer SQLite file can support,
   this is a database-engine decision, not a patch.** `app/db.py`'s own
   documentation anticipates this: on PostgreSQL/MySQL, the same correctness
   property is achieved with per-customer row locking
   (`rewards.lock_customer_for_redemption`'s `with_for_update()` branch)
   instead of a database-wide lock. This removes the cross-customer queueing
   in §4.1 entirely, since two different customers' checkouts no longer
   contend for the same lock. This is a larger change (migration, schema
   review) and should be scoped as planned work, not an incident-time fix.
5. **Add ingress-level rate limiting or a request queue cap** so that a load
   spike degrades as controlled latency rather than a wall of simultaneous
   lock failures. This does not increase capacity but improves how the
   system fails.

## 8. What not to do

- **Do not remove or bypass `BEGIN IMMEDIATE` / the redemption lock to
  "fix" throughput.** That reopens the exact concurrent-redemption race
  ADR-001 exists to close and converts a load incident into a correctness
  incident.
- **Do not silently retry a failed checkout inside the handler** without
  understanding whether the failure occurred before or after commit. The
  existing rollback-on-exception path already guarantees no partial state;
  an ad hoc retry layered on top risks double-submission unless idempotency
  is designed in.
- **Do not treat "add more app workers" as a complete fix** without also
  addressing §4.1/§4.2 — more workers contending for one SQLite write lock
  can *increase* observed lock-contention errors rather than reduce them.

## 9. Post-incident verification

1. Confirm no partial `orders`/`reward_ledger` rows exist for the incident
   window (§5, item 5).
2. Re-run `pytest tests/test_reward_ledger.py` and the Track B regression gate
   — a throughput fix must not change any functional outcome.
3. If a `busy_timeout` or transaction-scope change was made, re-verify the
   ADR-001 invariant under a deliberate concurrent-redemption test (two
   simultaneous redemptions against a shared balance) before considering the
   incident closed — this is the one test category Track B's suite does not
   currently include (see §4.7) and should be added as follow-up.
4. Record the incident against §4's factor numbers so Track D's governance
   record reflects that this is a known, structural scale limit rather than
   a recurring novel defect, and so a decision to move off SQLite (§7.4) has
   a documented trigger.

## References

[1] `app/routers/checkout.py` — transaction scope and its stated rationale.
[2] `app/db.py` — `BEGIN IMMEDIATE`, PRAGMA configuration, and the documented PostgreSQL/MySQL alternative.
[3] `app/services/rewards.py::lock_customer_for_redemption` — the row-locking branch this design anticipates for a non-SQLite dialect.
[4] ADR-001, *Reward Points Calculation and Storage*, Section 1 (force 2: concurrency) and Section 4 (consequences).
[5] Track B Regression Agent Report (`docs/track-b/regression-agent-report.md`), Section 7 — "not ready to gate production... workflow is not connected to a real deployment pipeline yet."
[6] `app/main.py` — documented dev run command; no production process configuration present in the repository.
[7] Companion runbook: *Reward Miscalculation* — see §6.6 for distinguishing a load-induced rejection from a genuine miscalculation.
