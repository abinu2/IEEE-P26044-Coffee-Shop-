# Interface Contract — Track A Feature Verticals

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | A (Build) |
| Parties | Allan (Profiles/Rewards, Checkout); [Teammate name] (Cart, Fulfillment) |
| Status | Draft — awaiting Section 4 sign-off |
| Reference implementation | `app/models.py` (schema), `app/schemas.py` (contracts) |

## 1. Purpose

This document fixes the shared interface between the two Track A feature
verticals — the database schema and the two API seams — prior to parallel
implementation. It is the day-one contract referenced in the project README.
Implementation of either vertical proceeds only after Section 4 is signed.

## 2. Shared database schema

| Table | Owner | Fields relied upon by both verticals |
|-------|-------|--------------------------------------|
| `customers` | Profiles/Rewards | `id`, `email` |
| `reward_ledger` | Profiles/Rewards | `id`, `customer_id`, `order_id`, `type` (`earn`/`redeem`/`reverse`), `points`, `created_at` |
| `carts` | Cart | `id`, `customer_id`, `status` |
| `cart_items` | Cart | `cart_id`, `item`, `qty`, `unit_price` |
| `orders` | Shared | `id`, `customer_id`, `cart_id`, `total`, `discount_applied`, `status` |
| `fulfillments` | Fulfillment | `id`, `order_id`, `state`, `scheduled_window`, transition history |

The `orders` table is created by the checkout vertical on order confirmation. Its
`status` field is subsequently updated by the fulfillment vertical. No other
cross-vertical writes to `orders` are permitted.

### 2.1 Fields added during implementation

The table above fixes the fields *relied upon by both verticals*. The reference
implementation in `app/models.py` adds the following, which are internal to the
Profiles/Rewards vertical and are recorded here so the table is not read as
exhaustive:

| Table | Added field | Reason |
|-------|-------------|--------|
| `orders` | `subtotal` | The contract lists `total` and `discount_applied`; `subtotal` is needed because points are earned on the pre-discount amount, and deriving it as `total + discount_applied` would silently break if a future charge (tax, delivery fee) enters `total`. |
| `reward_ledger` | `reverses_entry_id` | Identifies the entry a `reverse` row reverses, giving Track C an unambiguous audit chain and making double-reversal a constraint violation rather than a logic error. |
| `reward_ledger` | `reason` | Free-text provenance for an entry; consumed by the Track C runbook. |

`orders.status` values are fixed as `confirmed`, `in_preparation`, `completed`,
`cancelled`. Checkout writes only `confirmed`; every other value is written by
the Fulfillment vertical. **Confirm this set is sufficient for ADR-002 before
signing Section 4** — adding a state later is a schema change on shared data.

## 3. API contracts

### 3.1 Cart → Checkout

Produced by the Cart vertical; consumed by Checkout.

```
GET /cart/{cart_id}
→ 200 {
    "cart_id": str,
    "customer_id": str,
    "items": [{ "item": str, "qty": int, "unit_price": number }],
    "subtotal": number
  }
```

Checkout requires a stable subtotal and the `customer_id`, the latter to resolve
the customer's redeemable balance via the reward ledger.

### 3.2 Checkout → Fulfillment

Produced by the Checkout vertical; consumed by Fulfillment.

```
POST /fulfillment
  { "order_id": str, "delivery_address": str, "requested_window": str }
→ 201 {
    "fulfillment_id": str,
    "state": "scheduled",
    "scheduled_window": str
  }
```

The fulfillment vertical does not re-validate payment or rewards. Checkout
guarantees that an order passed to fulfillment is confirmed, paid, and valid.

## 4. Agreement

No parallel implementation begins until both rows below are signed. The purpose
of the gate is not ceremony: an unsigned seam means each vertical is built
against its own assumption of the other, and the mismatch surfaces at
integration when it is most expensive to correct.

| Item | Date | Profiles/Rewards owner | Cart/Fulfillment owner |
|------|------|------------------------|------------------------|
| Schema fixed | | | |
| Contracts fixed | | | |

### 4.1 Points requiring explicit agreement before signing

Settle each of these in the sign-off conversation and record the answer, rather
than discovering it at integration.

| # | Question | Bearing |
|---|----------|---------|
| 1 | Is `subtotal` in `GET /cart/{cart_id}` inclusive of tax and fees, or goods only? | Checkout does not recompute the cart subtotal; it earns points on whatever this number is. If it later includes tax, reward accrual changes without any rewards code changing. |
| 2 | Is the subtotal stable between the cart read and checkout, and what happens if the cart is edited mid-checkout? | Checkout prices from the value it read. Concurrent edit is the cart-side analogue of the concurrency force in ADR-001. |
| 3 | Who transitions the cart to `checked_out`, and when? | Checkout does not currently write to `carts`. If Cart expects it to, that is a cross-vertical write and must be added here explicitly. |
| 4 | Is the `orders.status` set in Section 2.1 sufficient for ADR-002? | Adding a state later is a shared-schema change. |
| 5 | On cancellation, who calls the reward reversal — Fulfillment, or Checkout on notification? | Reversal is implemented (`POST /orders/{order_id}/cancel`), but nothing triggers it yet. Until this is answered, cancelled orders keep their points. |
| 6 | Does Fulfillment ever need to read the reward ledger? | The stated answer is no; the ledger is private to this vertical and reaching into it directly would create a second consumer of a model ADR-001 assumes has one. |
