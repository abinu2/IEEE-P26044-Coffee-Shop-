# Requirements Specification — Cart and Fulfillment

| Field | Value |
|---|---|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | A (Build) |
| Feature verticals | Cart; Fulfillment |
| Author | Giovanni |
| Date | 2026-08-07 |

## Requirements

| ID | Requirement | Disposition |
|---|---|---|
| R-CA1 | A customer can create a non-empty cart containing named items with positive quantities and non-negative unit prices. | Edited: validation made explicit. |
| R-CA2 | Cart subtotal is the rounded sum of `quantity × unit price`; checkout consumes that value rather than repricing it. | Authored from the interface contract. |
| R-CA3 | A successfully checked-out cart cannot be checked out again. | Authored after reviewing the stubbed implementation. |
| R-F1 | A confirmed order can be scheduled once for a requested delivery window. | Edited: duplicate scheduling behavior made explicit. |
| R-F2 | Fulfillment progresses only `confirmed → in_preparation → completed`; cancellation is permitted before completion. | Edited: invalid and backward transitions are rejected. |
| R-F3 | Unknown orders, duplicate schedules, and invalid state transitions return explicit client-visible errors. | Authored. |

## AI-assumption gap log

| Assumption introduced during implementation | Resolution |
|---|---|
| Checkout may leave the cart open after order creation. | Rejected. Cart consumption now occurs in the same database transaction as order creation and reward changes. |
| Fulfillment state can be any string because the existing column is a string. | Rejected. The service enforces the order-state set already fixed in the shared contract. |
| A delivery address should be persisted even though it is absent from the shared schema. | Deferred. The API accepts the contract field, but changing the shared database requires agreement and a migration. This is an explicit limitation, not an accidental schema edit. |
| Fulfillment should accept the example `order_id` used by the earlier xfailed Track B test. | Rejected. Scheduling an unknown order returns 404; Track B should create a confirmed order before exercising this contract. |

## Acceptance evidence

Executable acceptance tests are in `tests/test_cart_fulfillment.py`. They cover
pricing, single-use checkout, scheduling, duplicate rejection, and forward-only
state transitions.
