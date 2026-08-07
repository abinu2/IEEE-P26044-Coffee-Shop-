# Increment and Coordination Log — Track A

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | A (Build) |
| Author | Allan |

## 1. Purpose

This log records each incremental delivery of Track A functionality and the
coordination communicated to the dependent tracks on delivery. Track A is
delivered in small increments so that Track B has live changes to test against
throughout the assignment rather than a single delivery at its conclusion.

## 2. Coordination requirements by track

| Track | Requires from Track A | Trigger |
|-------|-----------------------|---------|
| B — Regression | Notification of each endpoint delivered or changed, identifying the affected flow. Critical flows: checkout completion; correct reward calculation; redemption bounded at zero. | Every endpoint delivery or change |
| C — Runbooks | The reward-miscalculation failure mode from ADR-001; confirmation of actual code behavior against documented behavior; identification of flows not covered by Track B. | On delivery of rewards logic; on request |
| D — Governance | ADR-001 as a design-decision record; confirmation that the vertical contains no autonomous action. | On acceptance of ADR-001 |

## 3. Delivery sequence

| # | Increment | Endpoint(s) | Dependent-track notice |
|---|-----------|-------------|------------------------|
| 1 | Customer profiles | `POST /customers`, `GET /customers/{id}` | B |
| 2 | Cart pricing (Cart vertical) | — | — |
| 3 | Checkout without redemption | `POST /checkout` | B |
| 4 | Reward redemption in checkout | `POST /checkout` (redemption path) | B, C, D — delivery of ADR-001 logic |
| 5 | Fulfillment scheduling (Fulfillment vertical) | — | B, C |

### Increment 2 — Cart pricing — 2026-08-07

| Field | Entry |
|-------|-------|
| Endpoints delivered or changed | `POST /cart`, `GET /cart/{cart_id}`, `POST /checkout` |
| Flow affected | Cart creation/pricing; checkout now atomically marks a cart checked out |
| Notice issued to | Track B (recorded here; external notification still required) |
| Notes for dependent tracks | Add regression coverage for cart validation, subtotal, and prevention of duplicate checkout. |

### Increment 5 — Fulfillment scheduling — 2026-08-07

| Field | Entry |
|-------|-------|
| Endpoints delivered or changed | `POST /fulfillment`, `PATCH /fulfillment/{fulfillment_id}` |
| Flow affected | Schedule a confirmed order; advance it through valid fulfillment states |
| Notice issued to | Tracks B and C (recorded here; external notification still required) |
| Notes for dependent tracks | Scheduling rejects unknown/non-confirmed/duplicate orders. State transitions are forward-only. Delivery address is accepted but not persisted pending a shared-schema change. |

## 4. Delivery record

### Increment [n] — [summary] — [YYYY-MM-DD]

| Field | Entry |
|-------|-------|
| Endpoints delivered or changed | |
| Flow affected | |
| Notice issued to | |
| Notes for dependent tracks | |

## 5. Weekly coordination

A single weekly coordination note is issued covering: functionality delivered;
regression outcomes reported by Track B; runbook coverage required by Track C;
governance questions raised by Track D. A consolidated note is used in preference
to separate per-track updates.

## References

[1] ADR-001, *Reward Points Calculation and Storage.*
[2] Interface Contract — Track A Feature Verticals (`docs/comms/day-one-contract.md`).
