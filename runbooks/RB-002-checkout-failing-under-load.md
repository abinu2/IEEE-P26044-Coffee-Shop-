# RB-002 — Incident Runbook: Checkout Failing Under Load

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | C (Runbooks) — derived from Track A code |
| System | Checkout (`app/routers/checkout.py`); underlying persistence (`app/db.py`, `app/models.py`) |
| Source of truth | `app/db.py` (engine/session/transaction config), `app/routers/checkout.py` (transaction boundary), `app/services/rewards.py` (lock helper) |
| Governing design decision | ADR-001, *Reward Points Calculation and Storage* (concurrency force, §1 force 2; SQLite-vs-row-locking note, §4) |
| Related regression coverage | `tests/regression/test_track_b_regression_agent.py`, `.github/workflows/track-b-regression.yml`, `scripts/track_b_live_smoke.py` — **none of these exercise concurrent load** (see §9) |
| Status | Draft — pending human sign-off (see §10) |
| Generated | AI-drafted from repository state; requires named domain-validation owner before use in production (see §10) |

## 1. Purpose and scope

This runbook covers **checkout failing under load**: `POST /checkout`
returning errors, timing out, or stalling once concurrent request volume
rises, as distinct from a single-request checkout bug. It assumes the
endpoint works correctly under low concurrency (Track B's regression suite
already covers correctness — see its report, §1 items 5–10) and focuses on
what breaks specifically as concurrent traffic increases.

It does not cover reward arithmetic correctness (see RB-001), cart pricing
errors, or fulfillment scheduling — those are separate concerns even if they
surface through the same endpoint.

## 2. Why checkout is architecturally the narrowest point under load

Three decisions, each individually reasonable and each documented in the
repo, compound at checkout specifically:

1. **The whole checkout operation is one transaction, by design.**
   `checkout.py`'s module docstring is explicit: "The whole of checkout runs
   in a single transaction... or the concurrency guarantee is gone regardless
   of what the ADR says." That transaction spans a cart read, an order
   insert, the reward balance check, the ledger append, and the cart-status
   update — every one of these holds the write lock for the transaction's
   full duration, not just for its own statement.

2. **SQLite's `BEGIN IMMEDIATE` serializes *all* writers, not just
   contending ones.** `app/db.py`'s docstring states this cost outright:
   "the documented SQLAlchemy recipe for making SQLite serialize writers...
   The cost is that all writers serialize, which is acceptable at this
   scale." This is a global write lock, not a per-customer lock — two
   checkouts for two *different* customers still queue behind each other.
   `lock_customer_for_redemption()` in `rewards.py` additionally takes a
   per-customer row lock, but only on PostgreSQL/MySQL; on SQLite it is a
   documented no-op because `BEGIN IMMEDIATE` already serializes everything.

3. **No `busy_timeout` is configured.** `app/db.py` sets
   `PRAGMA foreign_keys=ON` and issues `BEGIN IMMEDIATE`, but sets no
   `PRAGMA busy_timeout`. SQLite's own default busy timeout is `0`: if a
   second writer's `BEGIN IMMEDIATE` cannot acquire the lock immediately, the
   underlying `sqlite3` driver raises `OperationalError: database is locked`
   at once rather than waiting. **This means the system's default behavior
   under any write concurrency at all is to fail fast, not to queue** — the
   opposite of what "serialize" usually implies operationally.

Put together: under load, checkout throughput is bounded by a single global
SQLite writer lock, held for the duration of a multi-step transaction, with
no configured grace period for a second writer to wait its turn. This is the
first thing to confirm or rule out in any checkout-under-load incident.

## 3. How this incident is likely to be reported

- `POST /checkout` returning `500` with `sqlite3.OperationalError: database
  is locked` (or the SQLAlchemy-wrapped equivalent) in application logs,
  correlated with a spike in concurrent requests.
- Checkout p95/p99 latency rising sharply as concurrent traffic increases,
  even without outright errors — requests queued behind the SQLite write
  lock rather than failing.
- `sqlalchemy.exc.TimeoutError` ("QueuePool limit... connection timed out")
  if concurrent requests exceed the SQLAlchemy connection pool size before
  they even reach the database lock.
- The `/health` endpoint responding normally (it does no database write)
  while `/checkout` degrades — a useful discriminator that the failure is
  write-path-specific, not a general outage.
- Load or traffic-spike windows (promotions, class demos, grading runs)
  correlating with the failure onset.

## 4. Immediate triage

1. **Confirm this is concurrency-related, not a single-request defect.**
   Check whether failures correlate with concurrent request volume (multiple
   `/checkout` calls within the same short window) rather than a specific
   payload. If a single sequential request also fails, this is not a
   load incident — investigate as a normal defect instead.
2. **Read the actual error class from logs**, since it points directly at
   which layer is saturated:
   - `database is locked` / `OperationalError` → SQLite write-lock
     contention (§2, points 1–3).
   - SQLAlchemy pool timeout → connection pool exhaustion (§5.2), a layer
     above the database lock.
   - Plain request timeouts with no driver-level error → the request is
     queued behind the lock and eventually exceeds an upstream (client or
     proxy) timeout before SQLite itself raises anything.
3. **Confirm which database is actually in use.** `COFFEE_DB_URL` selects
   the engine; everything in §2 is SQLite-specific. If the environment has
   been pointed at PostgreSQL/MySQL, the failure mode is different (see
   §5.4) and this runbook's SQLite-specific sections do not apply as
   written.
4. **Confirm the deployment topology.** The README's run instructions
   (`uvicorn app.main:app --reload`) describe a single process. If that is
   still how the incident environment is deployed, "load" may simply mean
   "more concurrent requests than one process was ever going to serve" —
   check this before assuming a code-level fix is needed.

## 5. Root-cause map

### 5.1 Global single-writer serialization (expected, not a bug, up to a point)
This is the baseline behavior `app/db.py` documents and accepts "at this
scale." If checkout under moderate concurrency shows *rising latency but
few or no outright errors*, this is the serialization working as designed —
requests are queuing for the write lock, not failing. The question to answer
is whether the current load has crossed from "acceptable at this scale" into
"unacceptable," which is a capacity/threshold judgment, not a defect to
patch line-by-line.

**Check:** correlate checkout latency against concurrent-request count. If
errors are near-zero but latency scales roughly linearly with concurrency,
this is §5.1, not §5.2 or §5.3.

### 5.2 Missing `busy_timeout` turning contention into immediate failures
Because no `PRAGMA busy_timeout` is set, the moment two `BEGIN IMMEDIATE`
transactions genuinely overlap, the loser fails immediately with
`database is locked` instead of waiting briefly for the lock to free. This
converts what should be a latency problem (§5.1) into an outright error
under even modest concurrency. This is very likely the dominant cause if
errors appear at low concurrency (e.g., 2–5 simultaneous checkouts) rather
than only under heavy load.

**Check:**
```
grep -n "busy_timeout" app/db.py   # currently absent
```
If absent, this is confirmed as a contributing cause; see §7 for the fix.

### 5.3 SQLAlchemy connection pool exhaustion
`create_engine()` in `app/db.py` is called with no `poolclass`, `pool_size`,
or `max_overflow` argument, so SQLAlchemy's defaults apply (`QueuePool`,
5 connections + 10 overflow for a file-backed engine, default pool timeout
30s). Under enough concurrent `/checkout` requests, callers can exhaust the
pool and wait up to the pool timeout for a connection *before* they ever
reach the SQLite write lock. This is a layer above §5.1/§5.2 and produces a
distinct error signature (`TimeoutError` from the pool, not from `sqlite3`).

**Check:** search logs for `QueuePool limit of size ... overflow ...
reached`. If present, the bottleneck is connection acquisition, not the
write lock itself — raising `busy_timeout` alone will not fix this.

### 5.4 Single-process deployment with no horizontal scaling
The documented run command (README §4a) starts one `uvicorn` process.
Nothing in the repository configures multiple workers, a process manager,
or a reverse proxy fanning out to several processes. If the incident
environment matches this default, "failing under load" may simply describe
the single-process ceiling being reached — check CPU/event-loop saturation
on the process itself, not just the database layer, before concluding the
database is the bottleneck.

### 5.5 Long-held transaction inflating lock duration
The checkout transaction, per its own docstring, deliberately spans cart
read → order insert → balance check → ledger append → cart status update,
all under one lock (§2, point 1). Any slowness inside that span — a slow
cart lookup, a slow reward query — extends how long every other writer
queues behind it. If profiling shows the transaction itself taking
noticeably longer under load (not just queuing time before it starts), look
for a specific step inside `checkout()` that has degraded, rather than
assuming the lock model itself is the fault.

### 5.6 Wrong database for the deployment's actual concurrency needs
ADR-001 §4 names the escape hatch directly: "Should it become material, a
materialized balance may be introduced... provided it is maintained as a
derived cache of the ledger," and separately, `rewards.py`'s
`lock_customer_for_redemption()` already contains the PostgreSQL/MySQL
per-row-lock path, dormant until `COFFEE_DB_URL` points at one of those
dialects. If checkout load has genuinely outgrown "student scale" (README
§1), the durable fix is switching the backing database, not tuning SQLite
pragmas — §5.2/§5.3's fixes are mitigations, not a substitute for this.

### 5.7 Client-side retries amplifying load during a lock-contention episode
`CheckoutRequest` carries no idempotency key. A client that times out
waiting for a slow-but-eventually-successful checkout and retries will, at
best, hit the `CartUnavailable` / 403 "cart already checked out" path
(`cart_client.mark_checked_out` only succeeds once) — but the retry itself
is additional write-path load landing on an already-contended system, and
during an active lock-contention incident this can turn a transient spike
into a sustained one. Check whether retry volume is elevated relative to
distinct checkout attempts before treating this as a purely server-side
capacity problem.

## 6. Diagnostic checklist (run in order)

1. Confirm the failure correlates with concurrency, not a specific payload
   (§4.1).
2. Classify the error signature: `database is locked` vs. pool timeout vs.
   plain request timeout (§4.2).
3. Confirm `COFFEE_DB_URL` — SQLite or a row-locking dialect (§4.3).
4. Confirm deployment topology — one process or several (§4.4, §5.4).
5. Check for `PRAGMA busy_timeout` in `app/db.py` (§5.2) — almost certainly
   absent; treat as the first, cheapest fix to test.
6. Check logs for `QueuePool` exhaustion messages (§5.3).
7. If neither §5.2 nor §5.3 shows in logs, profile the checkout transaction
   itself for a slow internal step (§5.5) before assuming the lock model is
   at fault.
8. Check whether retry traffic is inflating the load during the incident
   window (§5.7).

## 7. Immediate mitigations (while root cause is confirmed)

- **Set `PRAGMA busy_timeout` to a nonzero value** (e.g., a few seconds) as
  a same-day mitigation for §5.2 — this converts immediate lock failures
  into bounded waits, which is the serialization behavior the system was
  actually designed around. This does not fix throughput; it only stops
  contention from surfacing as hard errors.
- **Reduce concurrent checkout volume at the edge** (rate-limit or queue
  `/checkout` specifically) if the incident is active and neither of the
  above can be deployed immediately. `/health`, `/cart` reads, and other
  non-checkout endpoints do not need to be throttled — the bottleneck is
  specific to the write path described in §2.
- **Do not** respond to this incident by weakening the transaction boundary
  (e.g., splitting the balance check from the ledger append across commits)
  as a quick fix — that reopens the exact concurrent-redemption race
  ADR-001 §1 force 2 and RB-001 §5.2 exist to prevent. Any load-driven
  proposal that touches the transaction boundary in `checkout()` needs
  Track A sign-off against ADR-001 before deployment, not just Track C's.

## 8. Resolution paths by root cause

| Cause | Fix |
|---|---|
| §5.2 Missing `busy_timeout` | Add `PRAGMA busy_timeout=<n>ms` in `app/db.py`'s connect listener. Cheap, low-risk, addresses the most likely dominant cause. |
| §5.3 Pool exhaustion | Tune `pool_size`/`max_overflow` on `create_engine()`. Only helps up to the point where SQLite's own single-writer limit (§5.1) becomes binding again — verify with load testing (§9) that this isn't just moving the bottleneck. |
| §5.4 Single process | Add a process manager / multiple `uvicorn` workers behind a reverse proxy. Note this increases *concurrent pressure* on the still-single SQLite file — pair with §5.2 or plan §5.6 alongside it. |
| §5.5 Slow step inside the transaction | Profile and fix the specific step; do not shorten the transaction's correctness boundary to do so (§7). |
| §5.6 Genuine capacity outgrowth | Migrate `COFFEE_DB_URL` to PostgreSQL/MySQL; `lock_customer_for_redemption()` already has the per-row-lock path ready. This is the only fix that changes the ceiling itself rather than moving it. |
| §5.7 Retry amplification | Add an idempotency key to `CheckoutRequest` so retries are safe no-ops rather than new write attempts; coordinate with Track A since this is a schema/contract change (day-one contract §4). |

## 9. Known limitations of this runbook (carry forward per README §1)

- **No load or concurrency testing exists in the repository at all.**
  Track B's regression suite, CI workflow, and live-smoke script (§ header
  table) all exercise correctness at low/serial concurrency; none simulate
  concurrent `/checkout` traffic. Every severity threshold and "likely
  dominant cause" judgment in this runbook is therefore an inference from
  the code and its own documentation, not from an observed load test. This
  is the single biggest gap standing between this runbook and something
  that can be trusted without a human reviewing it against a real incident.
- This runbook should feed a concrete follow-up: a load/concurrency test
  added to Track B's suite (or a dedicated script alongside
  `scripts/track_b_live_smoke.py`) that exercises concurrent `/checkout`
  calls and asserts on error rate and latency, so future incidents in this
  category have a regression gate rather than only a runbook.
- Per ADR-001 §5's own finding about AI-assisted design artifacts, this
  runbook should be reviewed and signed off by a named accountable owner
  (the Track A owner, extended by analogy from the increment log's Track C
  row for reward miscalculation) before being treated as authoritative.

## 10. Closure criteria

An incident against this runbook is closed only when:

1. The specific root cause is identified against one of §5.1–§5.7 (or
   logged as a new cause and fed back into this runbook).
2. Checkout error rate and p95/p99 latency are confirmed restored to
   baseline across a representative concurrent-load window, not just a
   single successful retry.
3. If the fix touched the checkout transaction boundary or the concurrency
   model, `tests/test_reward_ledger.py`'s invariant suite is re-run and
   still passes — a load fix must not reopen the correctness guarantees
   RB-001 depends on.
