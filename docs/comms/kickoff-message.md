# Kickoff Message — Track A, to the Cart/Fulfillment owner

Sent at the start of Phase A, before either vertical begins parallel work. Kept
in the repository because the coordination artifacts are themselves part of the
TP.5 record, not incidental correspondence.

**Status:** [ ] drafted · [ ] sent on [YYYY-MM-DD] · [ ] contract signed

---

Hi [name],

I've pushed the Track A scaffold, and I'd like to get the day-one contract
signed before either of us starts building — it's the one thing that blocks us
both, and it should only take one sitting.

**What's in the repo now**

- `docs/comms/day-one-contract.md` — the schema and the two API seams. This is
  the document we need to agree on.
- `docs/adr/ADR-001-reward-points-calculation-and-storage.md` — my rewards
  decision, already made and written up.
- `app/` — a runnable skeleton: the schema, a checkout endpoint, and the reward
  ledger. `pip install -r requirements.txt && pytest` should pass for you.
- `docs/comms/increment-log.md` — the ship order and who gets told what.

**Why the contract has to be first.** We each own a vertical, and they meet in
exactly three places: the shared database schema, `cart → checkout`, and
`checkout → fulfillment`. If we start before those are fixed, we each build
against our own guess about the other's half, and we find out at integration —
which, given the timeline, is the worst possible moment. Signing it costs us an
hour now.

**What I need from you specifically**

1. **Confirm the schema.** I've written `app/models.py` to match Section 2 of
   the contract. I added three fields beyond what's listed — they're documented
   in Section 2.1 with the reasoning. `carts`, `cart_items` and `fulfillments`
   are in there only so the database builds and the foreign keys resolve;
   they're yours to replace. The fields named in Section 2 are the part I rely
   on and would need notice to change.

2. **Work through Section 4.1.** Six questions I couldn't answer alone. Two are
   worth flagging now:

   - *Is the cart subtotal goods-only, or does it include tax and fees?* I don't
     recompute pricing — I earn reward points on whatever number you hand me. So
     if that number changes meaning later, reward accrual changes with it and
     nothing in my code will look wrong.
   - *On cancellation, who triggers the reward reversal?* I've implemented it
     (`POST /orders/{order_id}/cancel`), but nothing calls it yet. Until we
     decide, a cancelled order keeps its points.

3. **Confirm the order states.** I've fixed `orders.status` at `confirmed`,
   `in_preparation`, `completed`, `cancelled`. Checkout only ever writes
   `confirmed`; the rest are yours. If ADR-002 needs a state that isn't there,
   now is when it's cheap to add.

**One thing to know about my side.** ADR-001 came out non-obvious, so it's worth
thirty seconds of your time: there is no stored points balance anywhere. The
balance is the sum of an append-only ledger, computed on read. That means
cancellation is just another ledger entry rather than a separate reversal path,
and concurrent redemptions can't race a shared counter. The practical
consequence for you is that you never need to update a balance — if something
should change a customer's points, it goes through my service, and the ledger
records it.

**Then we go in parallel.** Ship order is in `increment-log.md`: profiles →
cart pricing (yours) → checkout without redemption → redemption → fulfillment
scheduling (yours). I'll flag increment 4 loudly when it lands, because that's
where the ADR-001 logic goes live and Tracks C and D both build on it.

Can you look at `day-one-contract.md` before we meet? If Section 4.1 is
answered, signing is a formality.

Thanks,
Allan
